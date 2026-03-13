"""Orderly exchange implementation."""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
from typing import TYPE_CHECKING, Optional, Self

from httpx import RequestError, TimeoutException
from qasync import asyncSlot
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from plutus_terminal.core import keyring_manager
from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange import helpers as exchange_helpers
from plutus_terminal.core.exchange.base import ExchangeBase
from plutus_terminal.core.exchange.orderly.fetcher import OrderlyFetcher
from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRegistry
from plutus_terminal.core.exchange.orderly.models import (
    OrderlyCredentials,
    OrderlyNetwork,
    endpoints_for_network,
)
from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient
from plutus_terminal.core.exchange.orderly.trader import OrderlyTrader
from plutus_terminal.core.exchange.orderly.websocket import OrderlyWebsocketManager
from plutus_terminal.core.types_ import (
    ExchangeType,
    MessageLevel,
    NewAccountInfo,
    PerpsPosition,
    PerpsTradeDirection,
    PerpsTradeType,
    UserMessage,
)
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.core.config import AppConfig
    from plutus_terminal.core.exchange.types import OrderData, PnlDetails
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.message_bus import MessageBus


LOGGER = logging.getLogger(__name__)

_REQUIRED_ORDERLY_SECRETS = 3
_NETWORK_SECRET_INDEX = 3
_ORDERLY_KEY_PREFIX = "ed25519:"
_FALLBACK_MARKET_SYMBOLS = (
    "PERP_BTC_USDC",
    "PERP_ETH_USDC",
    "PERP_SOL_USDC",
)


class OrderlyExchange(ExchangeBase):
    """Class to interact with Orderly exchange."""

    def __init__(
        self,
        message_bus: MessageBus,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> None:
        """Initialize dependencies and account credentials."""
        super().__init__(message_bus=message_bus, pass_guard=pass_guard, app_config=app_config)
        keyring_account = self.app_config.current_keyring_account
        secrets = keyring_manager.get_exchange_password(str(keyring_account.username), pass_guard)

        if len(secrets) < _REQUIRED_ORDERLY_SECRETS:
            msg = "Orderly account requires Account ID, API Key and Secret."
            raise ValueError(msg)

        network = OrderlyNetwork.MAINNET
        if (
            len(secrets) > _NETWORK_SECRET_INDEX
            and secrets[_NETWORK_SECRET_INDEX].lower() == OrderlyNetwork.TESTNET.value
        ):
            network = OrderlyNetwork.TESTNET

        self._credentials = OrderlyCredentials(
            account_id=secrets[0],
            orderly_key=_normalize_orderly_key(secrets[1]),
            orderly_secret=secrets[2],
        )
        self._network = network
        self._endpoints = endpoints_for_network(network)
        self._pair_prefix = "Crypto."
        self._pair_separator = "/"
        self._pair_suffix = ""
        self._quote_symbol = "USDC"

    @classmethod
    async def create(
        cls,
        message_bus: MessageBus,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> Self:
        """Create class instance and initialize async dependencies."""
        instance = cls(message_bus, pass_guard, app_config)
        await instance.init_async()
        return instance

    async def init_async(self) -> None:
        """Initialize API clients, websocket manager, market metadata and services."""
        self._public_rest_client = OrderlyRestClient(self._endpoints.rest_url)
        self._private_rest_client = OrderlyRestClient(
            self._endpoints.rest_url,
            credentials=self._credentials,
        )
        self._market_registry = OrderlyMarketRegistry()
        try:
            await self._refresh_market_registry_with_retry()
        except (RequestError, TimeoutException):
            LOGGER.warning("Orderly market bootstrap unavailable, using fallback market symbols")
            self._market_registry.load_fallback_symbols(_FALLBACK_MARKET_SYMBOLS)

        self._ws_manager = OrderlyWebsocketManager(self._endpoints, self._credentials)
        self._fetcher = OrderlyFetcher(
            rest_client=self._private_rest_client,
            websocket_manager=self._ws_manager,
            market_registry=self._market_registry,
            message_bus=self.message_bus,
        )
        self._trader = OrderlyTrader(self._private_rest_client, self._market_registry)
        self._max_leverage = await self._fetch_max_leverage()

    @retry(
        retry=retry_if_exception_type((TimeoutException, RequestError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.3, max=2),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
        reraise=True,
    )
    async def _refresh_market_registry_with_retry(self) -> None:
        """Refresh market registry with tenacity retries for transient network failures."""
        await self._market_registry.refresh(self._public_rest_client)

    @property
    def trader(self) -> OrderlyTrader:
        """Return exchange trader implementation."""
        return self._trader

    @property
    def fetcher(self) -> OrderlyFetcher:
        """Return exchange fetcher implementation."""
        return self._fetcher

    @property
    def available_pairs(self) -> set[str]:
        """Return all exchange available pairs."""
        return self._market_registry.pairs

    @property
    def pair_prefix(self) -> str:
        """Return pair prefix."""
        return self._pair_prefix

    @property
    def pair_separator(self) -> str:
        """Return pair separator."""
        return self._pair_separator

    @property
    def quote_symbol(self) -> str:
        """Return quote symbol."""
        return self._quote_symbol

    @property
    def pair_suffix(self) -> str:
        """Return pair suffix."""
        return self._pair_suffix

    @property
    def cached_prices(self) -> dict:
        """Return cached prices."""
        return self.fetcher._cached_prices  # noqa: SLF001

    @property
    def stable_balance(self) -> Decimal:
        """Return trading balance used for sizing and liquidation previews."""
        trading_balance = getattr(self._fetcher, "trading_balance", None)
        if callable(trading_balance):
            balance = trading_balance()
            if isinstance(balance, Decimal):
                return balance
        return self.fetcher._balance_with_unsettled_pnl()  # noqa: SLF001

    def use_native_position_pnl(self) -> bool:
        """Use native unsettled PnL for positions-table display."""
        return True

    def calculate_pnl(
        self,
        perps_position: PerpsPosition,
        current_price: Optional[Decimal],
    ) -> PnlDetails:
        """Calculate Orderly PnL using the same semantics as the React SDK."""
        trade_collateral = perps_position["collateral_stable"]
        if trade_collateral <= Decimal(0):
            trade_collateral = perps_position["position_size_stable"] / perps_position["leverage"]

        unrealized_pnl = self.fetcher.calculate_unrealized_pnl(perps_position, current_price)
        opening_fee = self.fetcher.fetch_opening_fee(perps_position)
        funding_fee = self.fetcher.fetch_funding_fee(perps_position)
        unsettled_pnl = self.fetcher.calculate_sdk_unsettled_pnl(perps_position, current_price)
        closing_fee = self.fetcher.calculate_close_fee(perps_position, current_price)
        pnl_usd_after_fees = unsettled_pnl - closing_fee

        pnl_percentage = Decimal(0)
        if trade_collateral > Decimal(0):
            pnl_percentage = unrealized_pnl * Decimal(100) / trade_collateral

        pnl_percentage_after_fees = Decimal(0)
        if trade_collateral > Decimal(0):
            pnl_percentage_after_fees = pnl_usd_after_fees * Decimal(100) / trade_collateral

        return {
            "pnl_usd_before_fees": unrealized_pnl,
            "pnl_percentage_before_fees": pnl_percentage,
            "funding_fee_usd": funding_fee,
            "opening_fee_usd": opening_fee,
            "closing_fee_usd": closing_fee,
            "position_fee_usd": opening_fee,
            "pnl_usd_after_fees": pnl_usd_after_fees,
            "pnl_percentage_after_fees": pnl_percentage_after_fees,
            "pnl_label": "Unrealized PnL",
            "net_pnl_label": "Close-now PnL",
            "show_closing_fee": True,
        }

    @property
    def min_leverage(self) -> int:
        """Return minimum leverage supported by Orderly."""
        return 1

    @property
    def max_leverage(self) -> int:
        """Return maximum leverage for the account."""
        return self._max_leverage

    @property
    def min_order_size(self) -> Decimal:
        """Return global min order size among markets."""
        if not self.available_pairs:
            return Decimal(1)
        return min(
            self._market_registry.get_rule_by_pair(pair).min_notional
            for pair in self.available_pairs
        )

    @property
    def account_info(self) -> dict[str, object]:
        """Return account information displayed in UI."""
        account_id = self._credentials.account_id
        available_balance = getattr(self._fetcher, "available_balance", lambda: Decimal(0))()
        available_with_unsettled = getattr(
            self._fetcher,
            "available_balance_with_unsettled_pnl",
            lambda: available_balance,
        )()
        unsettled_pnl = getattr(self._fetcher, "unsettled_pnl_total", lambda: Decimal(0))()
        return {
            "Exchange": self.name().capitalize(),
            "Exchange Type": self.exchange_type().name,
            "Account": f"{account_id[:4]}...{account_id[-4:]}",
            "Network": self._network.value,
            "Free Balance": self.stable_balance,
            "Available Balance": available_balance,
            "Available Balance + Unsettled PnL": available_with_unsettled,
            "Unsettled PnL": unsettled_pnl,
        }

    async def fetch_prices(self) -> None:
        """Connect streams and start background watcher tasks."""
        await self.fetcher.start()
        await super().fetch_prices()

    async def is_ready_to_trade(self) -> bool:
        """Orderly API-key accounts are ready when authenticated."""
        return True

    async def approve_for_trading(self) -> None:
        """No on-chain approval is needed for Orderly CEX-style API trading."""

    @asyncSlot()
    async def set_leverage(self, coin: str, leverage: int) -> None:
        """Set leverage for a specific coin pair."""
        pair = self.format_pair_from_coin(coin)
        max_for_pair = self._max_leverage_for_pair(pair)
        bounded = max(self.min_leverage, min(max_for_pair, leverage))
        symbol = self._market_registry.get_symbol_for_pair(pair)
        await self.trader.set_leverage(symbol, bounded)
        self.app_config.leverage = bounded

    def _max_leverage_for_pair(self, pair: str) -> int:
        """Resolve effective max leverage for a pair from account and market limits."""
        market_rule = self._market_registry.get_rule_by_pair(pair)
        return min(self.max_leverage, market_rule.max_leverage)

    @asyncSlot()
    async def create_order(
        self,
        pair: str,
        amount: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> None:
        """Create new order for a pair."""
        price = await self._resolve_execution_price(pair, trade_type, execution_price)
        order_size_stable = amount * self.app_config.leverage
        symbol = self._market_registry.get_symbol_for_pair(pair)
        take_profit_target, stop_loss_target = self._resolve_attached_tp_sl_targets(
            execution_price=price,
            trade_direction=trade_direction,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )
        trade_arguments = {
            "symbol": symbol,
            "trade_direction": trade_direction,
            "trade_type": trade_type,
            "price": price,
            "size_stable": order_size_stable,
            "take_profit": take_profit_target,
            "stop_loss": stop_loss_target,
        }

        try:
            await self.trader.create_order(trade_arguments)
            info_message = UserMessage(
                text=f"Creating {trade_type.name} order for {pair}",
                level=MessageLevel.INFO,
                timeout_ms=5000,
            )
            self.message_bus.send_message.emit(info_message)
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to create order: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        await asyncio.gather(self.fetcher.fetch_all_orders(), self.fetcher.fetch_all_positions())
        self.message_bus.orders_fetched.emit(self.fetcher._cached_orders)  # noqa: SLF001
        self.message_bus.positions_fetched.emit(self.fetcher._cached_positions)  # noqa: SLF001

    @asyncSlot()
    async def edit_order(
        self,
        order_data: OrderData,
        new_size_stable: Decimal,
        new_execution_price: Decimal,
    ) -> None:
        """Edit existing order through native Orderly lifecycle endpoints."""
        trade_arguments = self._build_edit_trade_arguments(
            order_data=order_data,
            new_size_stable=new_size_stable,
            new_execution_price=new_execution_price,
        )

        try:
            await self.trader.edit_order(trade_arguments)
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to edit order: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        await self.fetcher.fetch_all_orders()
        self.message_bus.orders_fetched.emit(self.fetcher._cached_orders)  # noqa: SLF001

    @asyncSlot()
    async def create_reduce_order(
        self,
        pair: str,
        size: Decimal,
        collateral_delta: Decimal,  # noqa: ARG002
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal],
    ) -> None:
        """Create reduce-only order."""
        price = await self._resolve_execution_price(pair, trade_type, execution_price)
        symbol = self._market_registry.get_symbol_for_pair(pair)
        trade_arguments = {
            "symbol": symbol,
            "trade_direction": trade_direction,
            "trade_type": trade_type,
            "price": price,
            "size_stable": size,
            "reduce_only": True,
        }
        try:
            await self.trader.create_reduce_order(trade_arguments)
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to create reduce order: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        await self.fetcher.fetch_all_orders()
        self.message_bus.orders_fetched.emit(self.fetcher._cached_orders)  # noqa: SLF001

    @asyncSlot()
    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel one open order."""
        symbol = self._symbol_from_order(order_data)
        cancel_arguments = {
            "order_id": order_data["id"],
            "symbol": symbol,
            "trade_type": order_data["order_type"],
        }
        try:
            await self.trader.cancel_order(cancel_arguments)
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to cancel order: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        await self.fetcher.fetch_all_orders()
        self.message_bus.orders_fetched.emit(self.fetcher._cached_orders)  # noqa: SLF001

    @asyncSlot()
    async def close_position(self, perps_position: PerpsPosition) -> None:
        """Close position with reduce-only market order."""
        symbol = self._market_registry.get_symbol_for_pair(perps_position["pair"])
        position_extra = perps_position.get("extra", {})
        trade_arguments = {
            "symbol": symbol,
            "trade_direction": perps_position["trade_direction"],
            "trade_type": PerpsTradeType.MARKET,
            "price": perps_position["open_price"],
            "size_stable": perps_position["position_size_stable"],
            "reduce_only": True,
        }
        if isinstance(position_extra, dict):
            base_size = position_extra.get("base_size")
            if base_size is not None:
                trade_arguments["base_size"] = base_size
        try:
            await self.trader.close_position(trade_arguments)
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to close position: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        await self.fetcher._refresh_balance()  # noqa: SLF001
        await self.fetcher.fetch_all_positions()
        self.message_bus.positions_fetched.emit(self.fetcher._cached_positions)  # noqa: SLF001

    async def _resolve_execution_price(
        self,
        pair: str,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal],
    ) -> Decimal:
        """Resolve execution price for market or limit orders."""
        if execution_price is not None:
            return execution_price
        if trade_type is PerpsTradeType.MARKET:
            current = await self.fetcher.fetch_current_price(pair)
            return current["price"]
        msg = "Invalid execution price."
        raise TypeError(msg)

    async def _fetch_max_leverage(self) -> int:
        """Fetch max leverage from account info with safe default."""
        try:
            payload = await self._private_rest_client.request_private("GET", "/v1/client/info")
        except Exception:
            LOGGER.exception("Failed to fetch max leverage from Orderly client info")
            return 50
        max_leverage = payload.get("data", {}).get("max_leverage")
        if isinstance(max_leverage, int):
            return max_leverage
        if isinstance(max_leverage, str) and max_leverage:
            return int(max_leverage)
        return 50

    def _resolve_attached_tp_sl_targets(
        self,
        *,
        execution_price: Decimal,
        trade_direction: PerpsTradeDirection,
        take_profit: Optional[float],
        stop_loss: Optional[float],
    ) -> tuple[Decimal, Decimal]:
        """Resolve attached TP/SL targets while keeping paired submission explicit.

        If the caller explicitly passes both TP and SL percentages and both are non-zero,
        both targets are forwarded so the trader can build one native `TP_SL` payload.
        Otherwise only one attached exit target is emitted to preserve the existing
        single-order-at-a-time behavior.
        """
        take_profit_target = Decimal(0)
        stop_loss_target = Decimal(0)

        if take_profit is None and stop_loss is None:
            if self.app_config.take_profit != 0:
                take_profit_target = exchange_helpers.get_take_profit_target(
                    execution_price,
                    self.app_config.take_profit,
                    trade_direction,
                )
            elif self.app_config.stop_loss != 0:
                stop_loss_target = exchange_helpers.get_stop_loss_target(
                    execution_price,
                    self.app_config.stop_loss,
                    trade_direction,
                )
            return take_profit_target, stop_loss_target

        take_profit_target = exchange_helpers.get_take_profit_target(
            execution_price,
            take_profit,
            trade_direction,
        )
        stop_loss_target = exchange_helpers.get_stop_loss_target(
            execution_price,
            stop_loss,
            trade_direction,
        )
        if (
            take_profit is not None
            and stop_loss is not None
            and take_profit_target > 0
            and stop_loss_target > 0
        ):
            return take_profit_target, stop_loss_target
        if take_profit_target > 0:
            stop_loss_target = Decimal(0)
        elif stop_loss_target > 0:
            take_profit_target = Decimal(0)
        return take_profit_target, stop_loss_target

    def _symbol_from_order(self, order_data: OrderData) -> str:
        """Resolve orderly symbol from order data payload."""
        order_extra = order_data.get("extra", {})
        symbol = order_extra.get("symbol")
        if symbol is not None:
            return str(symbol)
        return self._market_registry.get_symbol_for_pair(order_data["pair"])

    def _build_edit_trade_arguments(
        self,
        *,
        order_data: OrderData,
        new_size_stable: Decimal,
        new_execution_price: Decimal,
    ) -> dict[str, object]:
        """Build native edit arguments while preserving existing TP/SL sibling state."""
        trade_arguments: dict[str, object] = {
            "order_id": order_data["id"],
            "symbol": self._symbol_from_order(order_data),
            "trade_direction": order_data["trade_direction"],
            "trade_type": order_data["order_type"],
            "price": new_execution_price,
            "size_stable": new_size_stable,
            "reduce_only": order_data["reduce_only"],
        }
        if not order_data["order_type"].is_tp_sl_order:
            return trade_arguments

        root_order_id = self._root_algo_order_id(order_data)
        if root_order_id is not None:
            trade_arguments["order_id"] = root_order_id

        take_profit, stop_loss = self._tp_sl_targets_for_edit(
            order_data=order_data,
            edited_trigger_price=new_execution_price,
        )
        trade_arguments["take_profit"] = take_profit
        trade_arguments["stop_loss"] = stop_loss
        return trade_arguments

    def _tp_sl_targets_for_edit(
        self,
        *,
        order_data: OrderData,
        edited_trigger_price: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Resolve full TP/SL target set for root-order edits."""
        take_profit = Decimal(0)
        stop_loss = Decimal(0)
        candidate_orders = self._tp_sl_sibling_orders(order_data)
        edited_order_id = str(order_data["id"])

        for candidate in candidate_orders:
            trigger_price = candidate["trigger_price"]
            if str(candidate["id"]) == edited_order_id:
                trigger_price = edited_trigger_price
            if candidate["order_type"] is PerpsTradeType.TRIGGER_TP:
                take_profit = trigger_price
            elif candidate["order_type"] is PerpsTradeType.TRIGGER_SL:
                stop_loss = trigger_price

        return take_profit, stop_loss

    def _tp_sl_sibling_orders(self, order_data: OrderData) -> list[OrderData]:
        """Return TP/SL siblings linked by the same Orderly root order id."""
        root_order_id = self._root_algo_order_id(order_data)
        if root_order_id is None:
            return [order_data]

        cached_orders = getattr(self.fetcher, "_cached_orders", [])
        matching_orders: list[OrderData] = []
        for candidate in cached_orders:
            if (
                candidate["pair"] != order_data["pair"]
                or not candidate["order_type"].is_tp_sl_order
            ):
                continue
            if self._root_algo_order_id(candidate) == root_order_id:
                matching_orders.append(candidate)
        return matching_orders or [order_data]

    @staticmethod
    def _root_algo_order_id(order_data: OrderData) -> str | None:
        """Return root algo order id when the parsed payload exposes one."""
        order_extra = order_data.get("extra", {})
        if not isinstance(order_extra, dict):
            return None
        root_order_id = order_extra.get("root_algo_order_id")
        if root_order_id in (None, ""):
            return None
        return str(root_order_id)

    @staticmethod
    def name() -> str:
        """Return exchange identifier."""
        return "orderly"

    @staticmethod
    def new_account_info() -> NewAccountInfo:
        """Provide required secrets for account creation dialog."""
        return {
            "referral_link": None,
            "secrets": [
                "Orderly Account ID",
                "Orderly API Key (orderly-key)",
                "Orderly Secret",
                "Network (mainnet|testnet)",
            ],
        }

    @staticmethod
    def exchange_type() -> ExchangeType:
        """Return exchange type."""
        return ExchangeType.DEX

    @staticmethod
    def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
        """Validate orderly account secret fields."""
        if len(secrets) < _REQUIRED_ORDERLY_SECRETS:
            return False, "Orderly requires account id, API key and secret."
        if not secrets[0].strip():
            return False, "Orderly account id is required."
        if not secrets[1].strip():
            return False, "Orderly API key is required."
        if not secrets[2].strip():
            return False, "Orderly secret is required."
        if len(secrets) > _NETWORK_SECRET_INDEX and secrets[
            _NETWORK_SECRET_INDEX
        ].strip().lower() not in {"", "mainnet", "testnet"}:
            return False, "Network must be 'mainnet' or 'testnet'."
        return True, "Valid orderly credentials."


def _normalize_orderly_key(orderly_key: str) -> str:
    """Normalize API key to include required Orderly prefix."""
    normalized_key = orderly_key.strip()
    if normalized_key.startswith(_ORDERLY_KEY_PREFIX):
        return normalized_key
    return f"{_ORDERLY_KEY_PREFIX}{normalized_key}"
