"""Foxify exchange fetcher."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from decimal import Decimal
import json
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Optional, Self

from httpx import AsyncClient, ConnectError, HTTPStatusError, ReadTimeout
import orjson
import pandas
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import (
    ConnectionClosedError,
    InvalidStatus,
    InvalidStatusCode,
)

from plutus_terminal.core.exchange.base import ExchangeFetcher
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.types import OrderData, PerpsTradeType
from plutus_terminal.core.exchange.web3.cycle_provider import build_cycle_provider
from plutus_terminal.core.types_ import (
    PerpsPosition,
    PerpsTradeDirection,
    PriceData,
    PriceHistory,
)
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from eth_typing import ChecksumAddress

    from plutus_terminal.core.exchange.base import ExchangeFetcherMessageBus

LOGGER = logging.getLogger(__name__)


class FoxifyFetcher(ExchangeFetcher):
    """Fetches market information for Foxify Exchange."""

    def __init__(
        self,
        pair_map: dict[str, str],
        web3_address: ChecksumAddress,
        message_bus: ExchangeFetcherMessageBus,
    ) -> None:
        """Initialize shared attributes.

        Args:
            pair_map (dict[str, dict[str, str]]): Dict with adress and pair.
            web3_address (ChecksumAddress): Web3 account address.
            message_bus (ExchangeFetcherMessageBus): Message bus.
        """
        LOGGER.info("Initialize FoxifyFetcher")
        self.aclient = AsyncClient()
        self.pair_map = pair_map
        self.web3_address = web3_address
        self.web3_provider = build_cycle_provider("Arbitrum One Fetcher")
        self.vault_contract = foxify_utils.build_vault_contract(self.web3_provider)
        self.order_book_contract = foxify_utils.build_order_book_contract(
            self.web3_provider,
        )
        self.stable_contract = foxify_utils.build_stable_contract(self.web3_provider)

        with Path.open(Path(__file__).parent.parent.joinpath("web3/pyth_feed_id.json")) as f:
            self.pyth_pair_id: dict = json.load(f)
        self.pyth_id_pair = {value: key for key, value in self.pyth_pair_id.items()}
        self._message_bus = message_bus
        self._socket: Optional[WebSocketClientProtocol] = None  # type: ignore
        self.connection_count: dict = defaultdict(int)
        self._cached_prices: dict[str, PriceData] = {}
        self._cached_stable_balance: Decimal = Decimal(0)
        self._cached_positions: list[PerpsPosition] = []
        self._cached_funding_rates: dict[str, dict[bool, int]] = {}
        self._synced = True
        self._goldsky_url = "https://api.goldsky.com/api/public/project_cllqn805a7tva38uh4n5r9ap6/subgraphs/palmswap-synthetic-stats/arbitrum_mainnet/gn"
        self.async_stop_event = asyncio.Event()

    @classmethod
    async def create(
        cls,
        pair_map: dict[str, str],
        web3_address: ChecksumAddress,
        message_bus: ExchangeFetcherMessageBus,
    ) -> Self:
        """Create class instance and init_async.

        Args:
            pair_map (dict[str, str]): Dict with adress and pair.
            web3_address (ChecksumAddress): Web3 account address.
            message_bus (ExchangeFetcherMessageBus): Message bus.

        Returns:
            FoxifyFetcher: Instance of FoxifyFetcher.
        """
        fetcher = cls(pair_map, web3_address, message_bus)
        await fetcher.init_async()
        return fetcher

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def init_async(self) -> None:
        """Initialize async shared attributes."""
        self.time_lock_contract = await foxify_utils.build_time_lock_contract(self.web3_provider)
        (
            _,
            self._vault_price_precision,
            self._funding_rate_precision,
            self._basis_points_divisor,
            self._margin_fee_basis_points,
            self._liquidation_fee,
        ) = await asyncio.gather(
            self._populate_funding_rates(),
            self.vault_contract.functions.PRICE_PRECISION().call(),
            self.vault_contract.functions.FUNDING_RATE_PRECISION().call(),
            self.vault_contract.functions.BASIS_POINTS_DIVISOR().call(),
            self.time_lock_contract.functions.marginFeeBasisPoints().call(),
            self.vault_contract.functions.liquidationFeeUsd().call(),
        )

    @retry(
        retry=(
            retry_if_exception_type(HTTPStatusError)
            | retry_if_exception_type(ReadTimeout)
            | retry_if_exception_type(ConnectError)
        ),
        reraise=True,
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_price_history(
        self,
        pair: str,
        from_timestamp: int,
        resolution: str,
    ) -> PriceHistory:
        """Fetch the price history on PYTH Network.

        Args:
            pair (str): Pair to fetch price for.
            from_timestamp (int): Timestamp for the leftmost bar.
            resolution (str): Bar resolution in seconds.

        Returns:
            PriceHistory: Dict with ohlcv.

        Raises:
            HTTPStatusError: If response is not successful. After tries.
        """
        request_url = "https://benchmarks.pyth.network/v1/shims/tradingview/history"
        now_timestamp = int(time.time())
        request_params = {
            "symbol": pair,
            "resolution": resolution,
            "from": from_timestamp,
            "to": now_timestamp,
        }

        response = await self.aclient.get(
            request_url,
            params=request_params,  # type: ignore
        )
        response.raise_for_status()

        data = response.json()

        price_history: PriceHistory = {
            "date": [pandas.Timestamp(t, unit="s") for t in data["t"]],
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
        }
        LOGGER.debug(
            "Fetched price history for %s from %s",
            pair,
            from_timestamp,
        )
        return price_history

    @retry(
        retry=(
            retry_if_exception_type(ConnectionClosedError)
            | retry_if_exception_type(InvalidStatus)
            | retry_if_exception_type(asyncio.TimeoutError)
            | retry_if_exception_type(InvalidStatusCode)
            | retry_if_exception_type(ConnectionAbortedError)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def websocket_connect(self) -> WebSocketClientProtocol:
        """Connect to websocket to fetch prices.

        Returns:
            WebSocketClientProtocol: Websocket connection.
        """
        if self._socket is None or self._socket.closed:
            self._socket = await connect(
                "wss://hermes.pyth.network/ws",
                ping_interval=10,
                ping_timeout=10,
            )
            LOGGER.info("Connected to hermes.pyth.network for Foxify")
            self._message_bus.price_synced.emit(True)
        return self._socket

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def _ensure_websocket_connection(self) -> None:
        """Ensure websocket is connected."""
        if self._socket is None or self._socket.closed:
            LOGGER.warning(
                "Websocket disconnected. Attempting to reconnect websocket...",
            )

            self._message_bus.price_synced.emit(False)
            await self.websocket_connect()
            await self.resubscribe_on_going_connections()

    async def subscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Subscribe to receive price updates for the given pair.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
            force (bool, optional): Force subscribe. Defaults to False.
        """
        await self._ensure_websocket_connection()

        self.connection_count[pair] += 1
        # Don't subscribe again if already connected.
        if self.connection_count[pair] > 1 and not force:
            return
        await self._socket.send(  # type: ignore
            json.dumps(
                {
                    "ids": [self.pyth_pair_id[pair]],
                    "type": "subscribe",
                },
            ),
        )
        LOGGER.info("Subscribed to receive price updates of: %s", pair)

    async def resubscribe_on_going_connections(self) -> None:
        """Resubscribe on going connections."""
        LOGGER.warning("Re-subscribing to on going connection...")
        for pair, count in self.connection_count.items():
            if count >= 1:
                await self.subscribe_to_price(pair, force=True)
                # Reduce 1 since this connection should already be present
                self.connection_count[pair] -= 1

    async def unsubscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Unsubscribe to receive price updates for the given pair.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
            force (bool, optional): Force unsubscribe. Defaults to False.
        """
        await self._ensure_websocket_connection()

        self.connection_count[pair] -= 1
        if self.connection_count[pair] > 0 and not force:
            return

        await self._socket.send(  # type: ignore
            json.dumps(
                {
                    "ids": [self.pyth_pair_id[pair]],
                    "type": "unsubscribe",
                },
            ),
        )
        self._cached_prices.pop(pair, None)

        self.connection_count[pair] = 0
        LOGGER.info("Unsubscribed to receive price updates of: %s", pair)

    async def receive_subscribed_prices(self) -> None:
        """Receive live data of subscribed prices from exchange."""
        await self._ensure_websocket_connection()
        while not self.async_stop_event.is_set():
            try:
                async for message in self._socket:  # type: ignore
                    data = orjson.loads(message)
                    if data.get("type", "") == "price_update":
                        pair = self.pyth_id_pair[f'0x{data["price_feed"]["id"]}']
                        self._cached_prices[pair] = PriceData(
                            {
                                "price": Decimal(
                                    int(data["price_feed"]["price"]["price"])
                                    * 10 ** int(data["price_feed"]["price"]["expo"]),
                                ),
                                "date": pandas.Timestamp(
                                    data["price_feed"]["price"]["publish_time"],
                                    unit="s",
                                ),
                            },
                        )
                        self._message_bus.subscribed_prices_signal.emit(
                            self._cached_prices,
                        )
            except (ConnectionClosedError, ConnectionAbortedError):
                LOGGER.exception("WebSocket connection closed unexpectely")
                await self._ensure_websocket_connection()
            except asyncio.CancelledError:
                LOGGER.debug("Receive subscribed prices cancelled.")
                raise
            except Exception:
                LOGGER.exception("Unexpected error while receiving prices")

    @retry(
        retry=(
            retry_if_exception_type(HTTPStatusError)
            | retry_if_exception_type(ReadTimeout)
            | retry_if_exception_type(ConnectError)
        ),
        reraise=True,
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_price_at_time(self, pair: str, timestamp: int) -> PriceData:
        """Fetch price at current time.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
            timestamp (int): Unix timestamp in seconds.

        Returns:
            PriceData: Price data for fetched pair.
        """
        LOGGER.debug("Fetching %s price at time: %s", pair, timestamp)
        request_url = f"https://hermes.pyth.network/v2/updates/price/{int(timestamp)}"
        request_params = {
            "ids[]": self.pyth_pair_id[pair],
        }

        response = await self.aclient.get(request_url, params=request_params)
        response.raise_for_status()

        data = response.json()
        return PriceData(
            {
                "price": Decimal(
                    int(data["parsed"][0]["price"]["price"])
                    * 10 ** int(data["parsed"][0]["price"]["expo"]),
                ),
                "date": data["parsed"][0]["price"]["publish_time"],
            },
        )

    async def watch_all_positions(self) -> None:
        """Watch all open positions for all available pairs."""
        while not self.async_stop_event.is_set():
            try:
                all_positions = await self.fetch_all_positions()
                self._message_bus.positions_signal.emit(all_positions)
            except (HTTPStatusError, ReadTimeout, ConnectError):
                LOGGER.exception("Unexpected error while fetching all positions")
                continue
            except asyncio.CancelledError:
                LOGGER.debug("Watch all positions cancelled.")
                raise
            finally:
                await asyncio.sleep(1)

    async def refresh_all_positions(self) -> None:
        """Refresh all open positions for all available pairs.

        This is used to force a refresh of all positions on the UI.
        """
        try:
            all_positions = await self.fetch_all_positions()
            self._message_bus.positions_signal.emit(all_positions)
        except (HTTPStatusError, ReadTimeout, ConnectError):
            LOGGER.exception("Unexpected error while fetching all positions")

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_all_positions(self) -> list[PerpsPosition]:
        """Fetch all open positions for all available pairs."""
        query = """
        query activePositionsByAccount($account: String!) {
          activePositions(
            where: {account: $account, collateral_not: "0"}
          ) {
            id
            averagePrice
            isLong
            size
            indexToken
            entryFundingRate
            collateral
            account
          }
        }
        """

        variables = {"account": self.web3_address.lower()}
        response = await self.aclient.post(
            self._goldsky_url,
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        data = response.json()
        positions_data = data["data"]["activePositions"]

        self._cached_positions.clear()
        for data in positions_data:
            pair = self.pair_map[data["indexToken"]]
            position_size = Decimal(data["size"]) / self._vault_price_precision
            leverage = position_size / (
                Decimal(data["collateral"]) / Decimal(self._vault_price_precision)
            )
            extra = {}
            extra["entry_funding_rate"] = data["entryFundingRate"]
            extra["index_token"] = data["indexToken"]
            collateral = position_size / leverage

            position = PerpsPosition(
                {
                    "pair": pair,
                    "id": data["id"],
                    "position_size_stable": position_size,
                    "collateral_stable": collateral,
                    "open_price": Decimal(data["averagePrice"]) / self._vault_price_precision,
                    "trade_direction": (
                        PerpsTradeDirection.LONG if data["isLong"] else PerpsTradeDirection.SHORT
                    ),
                    "leverage": round(leverage, 2),
                    "extra": extra,
                    "liquidation_price": Decimal(0),
                },
            )
            position["liquidation_price"] = self.calculate_liquidation_price(position)
            self._cached_positions.append(position)
        return self._cached_positions

    async def watch_all_orders(self) -> None:
        """Watch all open orders for all available pairs."""
        while not self.async_stop_event.is_set():
            try:
                all_orders = await self.fetch_all_orders()
                self._message_bus.orders_signal.emit(all_orders)
            except (HTTPStatusError, ReadTimeout, ConnectError):
                LOGGER.exception("Unexpected error while fetching all positions")
                continue
            except asyncio.CancelledError:
                LOGGER.debug("Watch all order cancelled.")
                raise
            finally:
                await asyncio.sleep(1)

    async def refresh_all_orders(self) -> None:
        """Refresh all open orders for all available pairs.

        This is used to force a refresh of all orders on the UI.
        """
        try:
            all_orders = await self.fetch_all_orders()
            self._message_bus.orders_signal.emit(all_orders)
        except (HTTPStatusError, ReadTimeout, ConnectError):
            LOGGER.exception("Unexpected error while fetching all positions")

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_all_orders(self) -> list[OrderData]:
        """Fetch all open orders."""
        query = """
        query WatchOrders($account: String!) {
          orders(

            orderBy: createdTimestamp
            orderDirection: desc

            where: {account: $account, status: open}
          ) {
            id
            index
            indexToken
            size
            type
            status
            createdTimestamp
          }
        }
        """
        variables = {"account": self.web3_address.lower()}
        response = await self.aclient.post(
            self._goldsky_url,
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        data = response.json()
        order_data = data["data"]["orders"]
        all_orders = []
        for order in order_data:
            func = self.order_book_contract.get_function_by_name(
                f"get{order['type'].capitalize()}Order",
            )
            chain_order = await func(
                self.web3_address,
                int(order["index"]),
            ).call()

            reduce_only = order["type"] == "decrease"
            is_long = chain_order[4]
            trigger_price = Decimal(chain_order[5])
            trigger_above_threshold = chain_order[6]
            extras = {
                "is_long": is_long,
                "trigger_above_threshold": trigger_above_threshold,
                "index": order["index"],
            }

            order_type = PerpsTradeType.LIMIT
            if trigger_price > 0 and reduce_only:
                if (is_long and trigger_above_threshold) or (
                    not is_long and not trigger_above_threshold
                ):
                    order_type = PerpsTradeType.TRIGGER_TP
                else:
                    order_type = PerpsTradeType.TRIGGER_SL

            all_orders.append(
                OrderData(
                    {
                        "id": order["id"],
                        "pair": self.pair_map[order["indexToken"]],
                        "trigger_price": trigger_price / self._vault_price_precision,
                        "size_stable": Decimal(order["size"]) / self._vault_price_precision,
                        "trade_direction": (
                            PerpsTradeDirection.LONG if is_long else PerpsTradeDirection.SHORT
                        ),
                        "order_type": order_type,
                        "reduce_only": reduce_only,
                        "extra": extras,
                    },
                ),
            )
        return all_orders

    def get_position_associated_with_order(self, order: OrderData) -> Optional[PerpsPosition]:
        """Get position associated with given order.

        Args:
            order (OrderData): Order to get position for.

        Returns:
            Optional[PerpsPosition]: Position associated with given order.
        """
        for position in self._cached_positions:
            if (
                order["pair"] == position["pair"]
                and order["trade_direction"] == position["trade_direction"]
            ):
                return position
        return None

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_current_price(self, pair: str) -> PriceData:
        """Fetch current price of given pair."""
        return await self.fetch_price_at_time(pair=pair, timestamp=int(time.time()))

    async def watch_stable_balance(self) -> None:
        """Watch stable balance."""
        while not self.async_stop_event.is_set():
            try:
                self._cached_stable_balance = await self.fetch_stable_balance()
                self._message_bus.balance_signal.emit(self._cached_stable_balance)
            except (HTTPStatusError, ReadTimeout, ConnectError):
                LOGGER.exception("Unexpected error while fetching stable balance.")
                continue
            except asyncio.CancelledError:
                LOGGER.debug("Watch all balance cancelled.")
                raise
            finally:
                await asyncio.sleep(2)

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_stable_balance(self) -> Decimal:
        """Fetch stable balance.

        Returns:
            Decimal: Balance in USD Stable Format.
        """
        balance = await self.stable_contract.functions.balanceOf(self.web3_address).call()

        return Decimal(balance) / 10**foxify_utils.USDC_DECIMAL_PLACES

    def calculate_margin_fee(self, position_size: Decimal) -> Decimal:
        """Calulate fee for a given position.

        Args:
            position_size (Decimal): Position size to get fee for.

        Returns:
            Decimal: Fee amount in USD Stable Format.
        """
        return (
            position_size
            * (
                self._basis_points_divisor
                - (self._basis_points_divisor - self._margin_fee_basis_points)
            )
        ) / (self._basis_points_divisor)

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_positions_funding_rates(self) -> None:
        """Fetch funding rate of cached positions.."""
        while True:
            await self._fetch_positions_funding_rates()
            await asyncio.sleep(5)

    async def _fetch_positions_funding_rates(self) -> None:
        """Fetch funding rate of cached positions.."""
        for position in self._cached_positions:
            position_extra = position.get("extra", None)
            if position_extra is None:
                LOGGER.error("Position extra data not found")
                continue

            self._cached_funding_rates[position["pair"]][position["trade_direction"].value] = int(
                await self.vault_contract.functions.cumulativeFundingRates(
                    self.web3_provider.to_checksum_address(
                        position_extra["index_token"],
                    ),
                    position["trade_direction"].value,
                ).call(),
            )

    async def _populate_funding_rates(self) -> None:
        """Fetch funding rate of cached positions."""
        tasks = []
        for direction in [
            PerpsTradeDirection.LONG.value,
            PerpsTradeDirection.SHORT.value,
        ]:
            for pair_address, pair in self.pair_map.items():
                self._cached_funding_rates.setdefault(pair, {})
                tasks.append(self._fetch_and_cache_funding_rate(pair, pair_address, direction))

        await asyncio.gather(*tasks)

    async def _fetch_and_cache_funding_rate(
        self,
        pair: str,
        pair_address: str,
        direction: bool,
    ) -> None:
        """Fetch and cache funding rate for a specific pair and direction.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
            pair_address (str): Pair address.
            direction (bool): Direction to fetch funding rate for.
        """
        rate = int(
            await self.vault_contract.functions.cumulativeFundingRates(
                self.web3_provider.to_checksum_address(pair_address),
                direction,
            ).call(),
        )
        self._cached_funding_rates[pair][direction] = rate

    def fetch_funding_fee(self, perps_position: PerpsPosition) -> Decimal:
        """Get funding fee for a given position.

        Args:
            perps_position (PerpsPosition): Position to get funding fee for.

        Returns:
            Decimal: Funding fee in USD Stable Format.
        """
        position_extra = perps_position.get("extra", None)
        # If no position extra data, consider no funding fee
        if position_extra is None:
            return Decimal(0)

        cumulative_funding_rate = self._cached_funding_rates[perps_position["pair"]][
            perps_position["trade_direction"].value
        ]

        funding_fee = cumulative_funding_rate - int(
            position_extra["entry_funding_rate"],
        )

        size = perps_position["position_size_stable"]
        return (size * funding_fee) / self._funding_rate_precision

    def calculate_liquidation_price(self, perps_position: PerpsPosition) -> Decimal:
        """Calculate liquidation price for a given position.

        This formula is not perfect and should be improved, values don't match
        the ones given on the front end, but are close.

        Args:
            perps_position (PerpsPosition): Position to get liquidation price for.

        Returns:
            Decimal: Liquidation price in USD Stable Format.
        """
        collateral = perps_position["collateral_stable"]
        funding_fee = self.fetch_funding_fee(perps_position)
        margin_fee = self.calculate_margin_fee(perps_position["position_size_stable"])
        liquidation_fee = Decimal(self._liquidation_fee / self._vault_price_precision)
        size = perps_position["position_size_stable"]
        trade_direction = perps_position["trade_direction"]
        total_fees = funding_fee + margin_fee + liquidation_fee

        open_price = perps_position["open_price"]

        liquidation_price_for_fees = self._calculate_liquidation_price_from_delta(
            total_fees,
            size,
            collateral,
            open_price,
            trade_direction,
        )

        liquidation_price_for_max_leverage = self._calculate_liquidation_price_from_delta(
            size * self._basis_points_divisor / 1000000,
            size,
            collateral,
            open_price,
            trade_direction,
        )

        if trade_direction == PerpsTradeDirection.LONG:
            return max(liquidation_price_for_fees, liquidation_price_for_max_leverage)
        return min(liquidation_price_for_fees, liquidation_price_for_max_leverage)

    def _calculate_liquidation_price_from_delta(
        self,
        total_fees: Decimal,
        size: Decimal,
        collateral: Decimal,
        open_price: Decimal,
        trade_direction: PerpsTradeDirection,
    ) -> Decimal:
        """Calculate liquidation price from delta.

        Args:
            total_fees (Decimal): Total fees (collateral + position fee + liquidation fee).
            size (Decimal): Position size.
            collateral (Decimal): Collateral.
            open_price (Decimal): Open price.
            trade_direction (PerpsTradeDirection): Trade direction.

        Returns:
            Decimal: Liquidation price in USD Stable Format.
        """
        if total_fees > collateral:
            if trade_direction == PerpsTradeDirection.LONG:
                return open_price - ((total_fees - collateral) * open_price / size)
            return open_price + ((total_fees - collateral) * open_price / size)

        if trade_direction == PerpsTradeDirection.LONG:
            return open_price - ((collateral - total_fees) * open_price / size)
        return open_price + ((collateral - total_fees) * open_price / size)

    def calculate_pnl_percent_before_fees(
        self,
        perps_position: PerpsPosition,
        current_price: Optional[Decimal],
    ) -> Decimal:
        """Calculate pnl percent for a given position.

        Args:
            perps_position (PerpsPosition): Position to get pnl for.
            current_price (Optional[Decimal]): Current price of the pair.

        Returns:
            Decimal: PNL in USD Stable Format.
        """
        open_price = perps_position["open_price"]
        trade_direction = perps_position["trade_direction"]
        leverage = perps_position["leverage"]
        trade_direction_multiplier = 1 if trade_direction == PerpsTradeDirection.LONG else -1
        if current_price is None:
            current_price = self._cached_prices[perps_position["pair"]]["price"]
        return ((current_price / open_price) - 1) * 100 * leverage * trade_direction_multiplier

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        self.async_stop_event.set()
        if self._socket is not None:
            await self._socket.close()
        await self.aclient.aclose()
