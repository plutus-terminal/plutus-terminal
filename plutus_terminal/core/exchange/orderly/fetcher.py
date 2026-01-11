"""Orderly Exchange Fetcher."""

from __future__ import annotations

import asyncio
import base64
from decimal import Decimal
import json
import logging
import time
from typing import TYPE_CHECKING, Optional, Self

from httpx import AsyncClient, ConnectError, HTTPStatusError, ReadTimeout
import orjson
import pandas
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    wait_exponential,
)
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import (
    ConnectionClosedError,
    InvalidStatus,
    InvalidStatusCode,
)

from plutus_terminal.core.exchange.base import ExchangeFetcher
from plutus_terminal.core.exchange.orderly import utils as orderly_utils
from plutus_terminal.core.exchange.types import OrderData, PerpsTradeType
from plutus_terminal.core.types_ import (
    PerpsPosition,
    PerpsTradeDirection,
    PriceData,
    PriceHistory,
)
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)


class OrderlyFetcher(ExchangeFetcher):
    """Fetches market information for Orderly Exchange."""

    def __init__(
        self,
        account_id: str,
        private_key: str,
        message_bus: MessageBus,
    ) -> None:
        """Initialize shared attributes."""
        LOGGER.info("Initialize OrderlyFetcher")
        self.aclient = AsyncClient()
        self.account_id = account_id
        self.signer = orderly_utils.OrderlySigner(account_id, private_key)
        self._message_bus = message_bus

        # Use Mainnet URLs
        self._api_url = orderly_utils.ORDERLY_MAINNET_API_URL
        self._public_ws_url = f"{orderly_utils.ORDERLY_MAINNET_WS_URL}/{account_id}"
        self._private_ws_url = f"{orderly_utils.ORDERLY_MAINNET_PRIVATE_WS_URL}/{account_id}"

        self._public_socket: WebSocketClientProtocol | None = None
        self._private_socket: WebSocketClientProtocol | None = None

        self.pair_map: dict[str, str] = {}
        self.inverted_pair_map: dict[str, str] = {}
        self.connection_count: dict = {}

        self._cached_prices: dict[str, PriceData] = {}
        self._cached_stable_balance: Decimal = Decimal(0)
        self._cached_positions: list[PerpsPosition] = []
        self._cached_orders: list[OrderData] = []

        self.async_stop_event = asyncio.Event()

    @classmethod
    async def create(
        cls,
        account_id: str,
        private_key: str,
        message_bus: MessageBus,
    ) -> Self:
        """Create class instance and init_async."""
        fetcher = cls(account_id, private_key, message_bus)
        await fetcher.init_async()
        return fetcher

    async def init_async(self) -> None:
        """Initialize async shared attributes."""
        await self.fetch_pair_map()

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
    async def fetch_pair_map(self) -> None:
        """Fetch available pairs from Orderly API."""
        LOGGER.info("Fetching available pairs from Orderly")
        # GET /v1/public/info
        url = f"{self._api_url}/v1/public/info"
        response = await self.aclient.get(url)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            msg = f"Orderly API Error: {data.get('message')}"
            raise ValueError(msg)

        rows = data.get("data", {}).get("rows", [])

        self.pair_map = {}
        for row in rows:
            # symbol: "PERP_BTC_USDC"
            symbol = row.get("symbol")
            if not symbol.startswith("PERP_"):
                continue

            # Parse coin name: PERP_BTC_USDC -> BTC
            parts = symbol.split("_")
            if len(parts) >= 3:
                coin = parts[1]
                quote = parts[2]  # USDC

                pair_name = f"{coin}/{quote}"
                self.pair_map[symbol] = pair_name
                self.connection_count[pair_name] = 0

        self.inverted_pair_map = {v: k for k, v in self.pair_map.items()}
        LOGGER.info("Fetched %s pairs", len(self.pair_map))

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
        to_timestamp: int,
        resolution: str,
    ) -> PriceHistory:
        """Fetch the price history from Orderly API."""
        symbol = self.inverted_pair_map.get(pair)
        if not symbol:
            msg = f"Unknown pair: {pair}"
            raise ValueError(msg)

        # Map resolution to Orderly format
        res_map = {
            "60": "1m",
            "300": "5m",
            "900": "15m",
            "1800": "30m",
            "3600": "1h",
            "86400": "1d",
            "604800": "1w",
        }
        type_res = res_map.get(resolution, "1m")

        request_url = f"{self._api_url}/v1/public/kline"
        request_params = {
            "symbol": symbol,
            "type": type_res,
            "from_timestamp": from_timestamp,
            "to_timestamp": to_timestamp,
        }

        response = await self.aclient.get(request_url, params=request_params)
        response.raise_for_status()

        data = response.json()
        if not data.get("success"):
            msg = f"Orderly API Error: {data.get('message')}"
            raise ValueError(msg)

        rows = data["data"]["rows"]
        timestamps = []
        opens = []
        highs = []
        lows = []
        closes = []

        for row in rows:
            timestamps.append(pandas.Timestamp(row["startTime"], unit="ms"))
            opens.append(float(row["open"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
            closes.append(float(row["close"]))

        price_history: PriceHistory = {
            "date": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        }
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
    async def public_websocket_connect(self) -> WebSocketClientProtocol:
        """Connect to public websocket."""
        if self._public_socket is None or self._public_socket.closed:
            self._public_socket = await connect(
                self._public_ws_url,
                ping_interval=10,
                ping_timeout=10,
            )
            LOGGER.info("Connected to Orderly Public WebSocket")
        return self._public_socket

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
    async def private_websocket_connect(self) -> WebSocketClientProtocol:
        """Connect to private websocket (authenticated)."""
        if self._private_socket is None or self._private_socket.closed:
            # Generate auth params
            timestamp = int(time.time() * 1000)
            message = str(timestamp)
            signature_bytes = self.signer.private_key.sign(message.encode("utf-8"))
            signature = (
                base64.urlsafe_b64encode(signature_bytes).decode("utf-8").rstrip("=")
            )

            # Extract public key
            from base58 import b58encode  # noqa: PLC0415
            from cryptography.hazmat.primitives import serialization  # noqa: PLC0415

            public_key_bytes = self.signer.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            orderly_key = f"ed25519:{b58encode(public_key_bytes).decode('utf-8')}"

            url = f"{self._private_ws_url}?orderly_key={orderly_key}&timestamp={timestamp}&sign={signature}"

            self._private_socket = await connect(
                url,
                ping_interval=10,
                ping_timeout=10,
            )
            LOGGER.info("Connected to Orderly Private WebSocket")
        return self._private_socket

    async def subscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Subscribe to ticker/trade updates."""
        await self._ensure_public_websocket_connection()

        if pair not in self.connection_count:
            self.connection_count[pair] = 0

        self.connection_count[pair] += 1
        if self.connection_count[pair] > 1 and not force:
            return

        symbol = self.inverted_pair_map.get(pair)
        if not symbol:
            return

        # Subscribe to ticker
        msg = {
            "id": f"subscribe_ticker_{symbol}",
            "topic": f"{symbol}@ticker",
            "event": "subscribe",
        }
        await self._public_socket.send(json.dumps(msg))
        LOGGER.info("Subscribed to ticker for %s", pair)

    async def unsubscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Unsubscribe."""
        if self._public_socket is None or self._public_socket.closed:
            return

        if pair in self.connection_count:
            self.connection_count[pair] -= 1

        if self.connection_count.get(pair, 0) > 0 and not force:
            return

        symbol = self.inverted_pair_map.get(pair)
        if not symbol:
            return

        msg = {
            "id": f"unsubscribe_ticker_{symbol}",
            "topic": f"{symbol}@ticker",
            "event": "unsubscribe",
        }
        await self._public_socket.send(json.dumps(msg))
        self._cached_prices.pop(pair, None)
        self.connection_count[pair] = 0

    async def _ensure_public_websocket_connection(self) -> None:
        if self._public_socket is None or self._public_socket.closed:
            await self.public_websocket_connect()
            # Resubscribe logic if needed
            for pair, count in self.connection_count.items():
                if count > 0:
                    await self.subscribe_to_price(pair, force=True)

    async def receive_subscribed_prices(self) -> None:
        """Listen to public websocket."""
        await self._ensure_public_websocket_connection()
        while not self.async_stop_event.is_set():
            try:
                async for message in self._public_socket:
                    data = orjson.loads(message)
                    if "topic" in data and "ticker" in data["topic"]:
                        # data example: { "topic": "PERP_BTC_USDC@ticker", "ts": 16123... , "data": { "symbol": "...", "price": ... } }
                        ticker = data["data"]
                        symbol = ticker["symbol"]
                        pair = self.pair_map.get(symbol)
                        if pair:
                            # Orderly ticker price is usually "close" or "last"
                            price = Decimal(str(ticker.get("close", 0)))
                            timestamp = data.get("ts", time.time() * 1000)

                            self._cached_prices[pair] = PriceData(
                                {
                                    "price": price,
                                    "date": pandas.Timestamp(timestamp, unit="ms"),
                                },
                            )
                            self._message_bus.subscribed_prices_fetched.emit(
                                self._cached_prices,
                            )
                    elif "event" in data and data["event"] == "ping":
                        await self._public_socket.send(json.dumps({"event": "pong"}))

            except (ConnectionClosedError, ConnectionAbortedError):
                LOGGER.exception("Public WS closed unexpectedly")
                await self._ensure_public_websocket_connection()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Error in receive_subscribed_prices")
                await asyncio.sleep(1)

    async def watch_all_positions(self) -> None:
        """Subscribe to private user data streams (positions, orders, balance)."""
        await self._ensure_private_websocket_connection()

        # Topics: position, executionreport, balance
        topics = ["position", "executionreport", "balance"]
        for topic in topics:
            msg = {
                "id": f"subscribe_{topic}",
                "topic": topic,
                "event": "subscribe",
            }
            await self._private_socket.send(json.dumps(msg))

        # Also need to listen... loop is below
        while not self.async_stop_event.is_set():
            try:
                await self._process_private_websocket_message()
            except (ConnectionClosedError, ConnectionAbortedError):
                LOGGER.exception("Private WS closed unexpectedly")
                await self._ensure_private_websocket_connection()
                # Resubscribe
                for topic in topics:
                    msg = {
                        "id": f"subscribe_{topic}",
                        "topic": topic,
                        "event": "subscribe",
                    }
                    await self._private_socket.send(json.dumps(msg))
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Error in watch_all_positions loop")
                await asyncio.sleep(1)

    async def _process_private_websocket_message(self) -> None:
        async for message in self._private_socket:
            data = orjson.loads(message)
            topic = data.get("topic", "")

            if topic == "position":
                self._process_positions(data["data"])
            elif topic == "executionreport":
                self._process_order_update(data["data"])
            elif topic == "balance":
                self._process_balance(data["data"])
            elif data.get("event") == "ping":
                await self._private_socket.send(json.dumps({"event": "pong"}))

    async def _ensure_private_websocket_connection(self) -> None:
        if self._private_socket is None or self._private_socket.closed:
            await self.private_websocket_connect()

    def _process_positions(self, positions_data: dict | list) -> None:
        if isinstance(positions_data, dict):
            positions_data = [positions_data]

        current_positions_map = {p["pair"]: p for p in self._cached_positions}

        for pos in positions_data:
            symbol = pos["symbol"]
            pair = self.pair_map.get(symbol)
            if not pair:
                continue

            qty = float(pos["positionQty"])
            if qty == 0:
                current_positions_map.pop(pair, None)
                continue

            entry_price = float(pos["averageOpenPrice"])
            # Update: Calculate position_size_stable (USD value)
            # Orderly returns qty in base asset.
            # position_size_stable = abs(qty) * entry_price
            # This fixes the mismatch where Plutus expects USD value.

            position_size_usd = abs(qty) * entry_price

            is_long = qty > 0
            # size in base asset not stored in PerpsPosition but can be inferred or stored in extra if needed.

            perps_pos = PerpsPosition(
                {
                    "pair": pair,
                    "id": symbol,  # Use symbol as ID
                    "position_size_stable": Decimal(str(position_size_usd)),
                    "collateral_stable": Decimal(0),  # Placeholder for cross margin
                    "open_price": Decimal(str(entry_price)),
                    "trade_direction": PerpsTradeDirection.LONG
                    if is_long
                    else PerpsTradeDirection.SHORT,
                    "leverage": 1,  # Placeholder
                    "liquidation_price": Decimal(str(pos.get("estLiqPrice", 0))),
                    "extra": pos,  # Store raw data
                },
            )
            current_positions_map[pair] = perps_pos

        self._cached_positions = list(current_positions_map.values())
        self._message_bus.positions_fetched.emit(self._cached_positions)

    def _process_order_update(self, order_data: dict) -> None:
        symbol = order_data["symbol"]
        pair = self.pair_map.get(symbol)
        if not pair:
            return

        order_id = str(order_data["orderId"])
        status = order_data["status"]

        if status in ["FILLED", "CANCELLED", "REJECTED"]:
            self._cached_orders = [
                o for o in self._cached_orders if str(o["id"]) != order_id
            ]
        elif status in {"NEW", "PARTIAL_FILLED"}:
            self._add_or_update_order(order_data, pair, order_id)

        self._message_bus.orders_fetched.emit(self._cached_orders)

    def _add_or_update_order(self, order_data: dict, pair: str, order_id: str) -> None:
        existing = next(
            (o for o in self._cached_orders if str(o["id"]) == order_id),
            None,
        )

        is_long = order_data["side"] == "BUY"
        o_type = order_data.get("type", "LIMIT")
        trade_type = (
            PerpsTradeType.MARKET if o_type == "MARKET" else PerpsTradeType.LIMIT
        )
        reduce_only = order_data.get("reduceOnly", False)

        new_order = OrderData(
            {
                "id": order_id,
                "pair": pair,
                "trigger_price": Decimal(str(order_data.get("price", 0))),
                "size_stable": Decimal(str(order_data.get("quantity", 0))),
                "trade_direction": PerpsTradeDirection.LONG
                if is_long
                else PerpsTradeDirection.SHORT,
                "order_type": trade_type,
                "reduce_only": reduce_only,
                "extra": order_data,
            },
        )

        # Update: size_stable should be USD value?
        # Plutus usually displays order size in USD or Asset?
        # If I look at Foxify, it stored "size_stable" as USD value.
        # Orderly order_data has "quantity" (base asset).
        # We need to estimate USD value for "size_stable".

        price = Decimal(str(order_data.get("price", 0)))
        quantity = Decimal(str(order_data.get("quantity", 0)))

        size_usd = Decimal(0)
        if price > 0:
            size_usd = quantity * price
        else:
            current_price = self._cached_prices.get(pair)
            if current_price:
                size_usd = quantity * current_price["price"]

        new_order["size_stable"] = size_usd

        if existing:
            self._cached_orders = [
                new_order if str(o["id"]) == order_id else o for o in self._cached_orders
            ]
        else:
            self._cached_orders.append(new_order)

    def _process_balance(self, balance_data: dict) -> None:
        holdings = balance_data.get("holding", [])
        for h in holdings:
            if h["token"] == "USDC":  # noqa: S105
                self._cached_stable_balance = Decimal(str(h["holding"]))
                self._message_bus.balance_fetched.emit(self._cached_stable_balance)
                break

    async def fetch_all_positions(self) -> list[PerpsPosition]:
        """Fetch all positions."""
        return self._cached_positions

    async def fetch_all_orders(self) -> list[OrderData]:
        """Fetch all orders."""
        return self._cached_orders

    async def watch_all_orders(self) -> None:
        """Watch all orders."""
        # Handled in watch_all_positions (same websocket stream)

    async def watch_stable_balance(self) -> None:
        """Watch stable balance."""
        # Handled in watch_all_positions (same websocket stream)

    async def fetch_current_price(self, pair: str) -> PriceData:
        """Fetch current price."""
        if pair in self._cached_prices:
            return self._cached_prices[pair]

        # Fallback to REST API
        # GET /v1/public/market_info/ticker
        # symbol = self.inverted_pair_map[pair]
        symbol = self.inverted_pair_map.get(pair)
        if not symbol:
             return PriceData({"price": Decimal(0), "date": pandas.Timestamp.now()})

        url = f"{self._api_url}/v1/public/market_info/ticker"
        try:
            resp = await self.aclient.get(url, params={"symbol": symbol})
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                # data["data"]["rows"] -> list
                # or single dict? Ticker endpoint usually returns single if symbol passed?
                # Docs: GET /v1/public/market_info/ticker?symbol=PERP_BTC_USDC
                # Response: { "data": { "symbol": ..., "close": ... } }
                # (Note: docs structure might vary, let's assume standard response)

                ticker_data = data.get("data", {})
                price = Decimal(str(ticker_data.get("close", 0)))
                # Update cache
                self._cached_prices[pair] = PriceData({
                    "price": price,
                    "date": pandas.Timestamp.now() # Ticker might have TS?
                })
                return self._cached_prices[pair]
        except Exception:
            LOGGER.exception("Failed to fetch current price via REST")

        return PriceData({"price": Decimal(0), "date": pandas.Timestamp.now()})

    async def fetch_price_at_time(self, pair: str, timestamp: int) -> PriceData:  # noqa: ARG002
        """Fetch price at time."""
        # Not easily supported by Orderly API without kline?
        # Used for PnL history maybe?
        return PriceData(
            {"price": Decimal(0), "date": pandas.Timestamp(timestamp, unit="s")},
        )

    async def fetch_stable_balance(self) -> Decimal:
        """Fetch stable balance."""
        return self._cached_stable_balance

    def calculate_margin_fee(self, position_size: Decimal) -> Decimal:
        """Calculate margin fee."""
        # Orderly fee is usually around 0.06% taker, 0.03% maker (varies)
        # Using 0.06% as conservative estimate
        return position_size * Decimal("0.0006")

    def fetch_funding_fee(self, perps_position: PerpsPosition) -> Decimal:  # noqa: ARG002
        """Fetch funding fee."""
        # TODO: Calculate funding fee from entry point?
        return Decimal(0)

    def calculate_liquidation_price(self, perps_position: PerpsPosition) -> Decimal:
        """Calculate liquidation price."""
        return perps_position["liquidation_price"]

    def calculate_pnl_percent_before_fees(
        self,
        perps_position: PerpsPosition,
        current_price: Optional[Decimal],
    ) -> Decimal:
        """Calculate pnl percent before fees."""
        open_price = perps_position["open_price"]
        if open_price == 0:
            return Decimal(0)

        trade_direction = perps_position["trade_direction"]
        leverage = perps_position["leverage"]  # Note: we defaulted this to 1

        # If we want effective PnL %, we should use the actual price movement
        if current_price is None:
            if perps_position["pair"] in self._cached_prices:
                current_price = self._cached_prices[perps_position["pair"]]["price"]
            else:
                return Decimal(0)

        diff = (current_price - open_price) / open_price
        if trade_direction == PerpsTradeDirection.SHORT:
            diff = -diff

        return diff * 100 * leverage

    async def stop_async(self) -> None:
        """Stop async tasks."""
        self.async_stop_event.set()
        if self._public_socket:
            await self._public_socket.close()
        if self._private_socket:
            await self._private_socket.close()
        await self.aclient.aclose()

    @property
    def cached_prices(self) -> dict:
        """Return cached prices."""
        return self._cached_prices

    @property
    def cached_stable_balance(self) -> Decimal:
        """Return cached stable balance."""
        return self._cached_stable_balance
