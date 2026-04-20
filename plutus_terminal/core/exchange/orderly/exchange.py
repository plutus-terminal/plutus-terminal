"""Orderly exchange implementation."""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
import re
from typing import TYPE_CHECKING, Optional, Self

from httpx import HTTPStatusError, RequestError, TimeoutException
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
from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRequestError, OrderlyRestClient
from plutus_terminal.core.exchange.orderly.tp_sl_coordinator import (
    OrderlyTpSlCoordinator,
    PositionSnapshot,
    snapshot_from_position,
)
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
_LEVERAGE_RANGE_PATTERN = re.compile(r"between\s+(\d+)x\s+and\s+(\d+)x", re.IGNORECASE)
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
        except (HTTPStatusError, OrderlyRequestError, RequestError, TimeoutException):
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
        self._tp_sl_coordinator = OrderlyTpSlCoordinator()
        self._tp_sl_reconcile_task: asyncio.Task[None] | None = None
        self._connect_tp_sl_reconciliation()
        self._max_leverage = max(
            await self._fetch_max_leverage(),
            getattr(self._market_registry, "max_leverage", 0),
        )

    @retry(
        retry=retry_if_exception_type(
            (TimeoutException, RequestError, HTTPStatusError, OrderlyRequestError)
        ),
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
        current_price: Decimal | None,
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
        """Return the highest leverage exposed by current Orderly metadata."""
        return self._max_leverage

    def max_leverage_for_pair(self, pair: str) -> int:
        """Return the current Orderly leverage cap for a specific pair."""
        market_rule = self._market_registry.get_rule_by_pair(pair)
        return market_rule.max_leverage

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
        max_for_pair = self.max_leverage_for_pair(pair)
        bounded = max(self.min_leverage, min(max_for_pair, leverage))
        symbol = self._market_registry.get_symbol_for_pair(pair)
        try:
            await self.trader.set_leverage(symbol, bounded)
        except TransactionFailedError as error:
            fallback_max_leverage = _extract_max_leverage_from_error(error)
            if fallback_max_leverage is None or fallback_max_leverage >= bounded:
                raise

            LOGGER.warning(
                "Orderly rejected %s leverage=%sx; retrying with server limit=%sx",
                pair,
                bounded,
                fallback_max_leverage,
            )
            self._market_registry.update_pair_max_leverage(pair, fallback_max_leverage)
            bounded = max(self.min_leverage, min(fallback_max_leverage, leverage))
            await self.trader.set_leverage(symbol, bounded)
        self.app_config.leverage = bounded

    @asyncSlot()
    async def create_order(
        self,
        pair: str,
        amount: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Decimal | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
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
        deferred_tp_sl_message: str | None = None
        original_position = self._current_position_snapshot(
            pair=pair, trade_direction=trade_direction
        )

        try:
            result = await self.trader.create_order(trade_arguments)
            if trade_type.is_regular_order and (take_profit_target > 0 or stop_loss_target > 0):
                deferred_tp_sl_message = await self._handle_deferred_entry_tp_sl(
                    pair=pair,
                    symbol=symbol,
                    trade_direction=trade_direction,
                    trade_type=trade_type,
                    result=result,
                    take_profit_price=take_profit_target if take_profit_target > 0 else None,
                    stop_loss_price=stop_loss_target if stop_loss_target > 0 else None,
                    reference_price=price,
                    original_position=original_position,
                )
            if deferred_tp_sl_message is not None:
                message_text = deferred_tp_sl_message
                message_level = MessageLevel.INFO
            else:
                message_text = f"Creating {trade_type.name} order for {pair}"
                message_level = MessageLevel.INFO

            self.message_bus.send_message.emit(
                UserMessage(
                    text=message_text,
                    level=message_level,
                    timeout_ms=5000,
                ),
            )
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to create order: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        await self._refresh_after_order_submission(pair=pair, refresh_positions=True)

    async def _handle_deferred_entry_tp_sl(
        self,
        *,
        pair: str,
        symbol: str,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        result: object,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
        reference_price: Decimal,
        original_position: PositionSnapshot | None,
    ) -> str:
        """Queue and reconcile deferred TP/SL for Orderly regular entry orders."""
        coordinator = self._ensure_tp_sl_coordinator()
        coordinator.enqueue(
            coordinator.create_intent(
                pair=pair,
                symbol=symbol,
                trade_direction=trade_direction,
                trade_type=trade_type,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
                reference_price=reference_price,
                source_order_id=_extract_source_order_id(result),
                original_position=original_position,
            )
        )

        await self._refresh_after_order_submission(pair=pair, refresh_positions=True)
        applied_count = await self._reconcile_pending_tp_sl_intents(notify=False)
        if applied_count > 0:
            return f"Created {trade_type.name} order for {pair} and applied TP/SL"
        if trade_type is PerpsTradeType.MARKET:
            return f"Created MARKET order for {pair}. Applying TP/SL after fill."
        return f"Created {trade_type.name} order for {pair}. TP/SL will activate after fill."

    def _ensure_tp_sl_coordinator(self) -> OrderlyTpSlCoordinator:
        """Return deferred TP/SL coordinator, creating one lazily in tests."""
        coordinator = getattr(self, "_tp_sl_coordinator", None)
        if coordinator is None:
            coordinator = OrderlyTpSlCoordinator()
            self._tp_sl_coordinator = coordinator
        return coordinator

    def _connect_tp_sl_reconciliation(self) -> None:
        """Reconnect deferred TP/SL checks after live position updates."""
        positions_signal = getattr(self.message_bus, "positions_fetched", None)
        connect = getattr(positions_signal, "connect", None)
        if callable(connect):
            connect(self._schedule_tp_sl_reconciliation)

    def _schedule_tp_sl_reconciliation(self, *_args: object) -> None:
        """Schedule async TP/SL reconciliation from sync signal callbacks."""
        task = getattr(self, "_tp_sl_reconcile_task", None)
        if task is not None and not task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._tp_sl_reconcile_task = loop.create_task(self._reconcile_pending_tp_sl_intents())

    async def _reconcile_pending_tp_sl_intents(self, *, notify: bool = True) -> int:
        """Apply pending TP/SL intents when matching positions appear."""
        coordinator = self._ensure_tp_sl_coordinator()
        applied_count = 0

        for intent in coordinator.pop_expired_intents():
            if notify:
                self._emit_tp_sl_deferred_warning(
                    pair=intent.pair,
                    reason="TP/SL could not be applied automatically before the retry window expired.",
                )

        current_positions = list(getattr(self.fetcher, "_cached_positions", []))
        for intent, position in coordinator.pop_ready_intents(positions=current_positions):
            await self.submit_position_tp_sl(
                pair=intent.pair,
                size_stable=position["position_size_stable"],
                trade_direction=intent.trade_direction,
                take_profit_price=intent.take_profit_price,
                stop_loss_price=intent.stop_loss_price,
                reference_price=intent.reference_price,
                base_size=self._position_base_size(position),
            )
            applied_count += 1

        current_orders = list(getattr(self.fetcher, "_cached_orders", []))
        for intent in coordinator.pop_abandoned_limit_intents(open_orders=current_orders):
            if notify:
                self._emit_tp_sl_deferred_warning(
                    pair=intent.pair,
                    reason="The parent order closed before TP/SL could activate.",
                )
        return applied_count

    def _current_position_snapshot(
        self,
        *,
        pair: str,
        trade_direction: PerpsTradeDirection,
    ) -> PositionSnapshot | None:
        """Return snapshot of current same-side position before entry submission."""
        position = self._position_for_pair_direction(pair=pair, trade_direction=trade_direction)
        if position is None:
            return None
        return snapshot_from_position(position)

    def _position_for_pair_direction(
        self,
        *,
        pair: str,
        trade_direction: PerpsTradeDirection,
    ) -> PerpsPosition | None:
        """Return cached position for one pair and direction when present."""
        for position in getattr(self.fetcher, "_cached_positions", []):
            if not isinstance(position, dict):
                continue
            position_pair = position.get("pair")
            position_direction = position.get("trade_direction")
            if position_pair == pair and position_direction is trade_direction:
                return position
        return None

    @staticmethod
    def _position_base_size(position: PerpsPosition) -> Decimal | None:
        """Return parsed base size from one cached position."""
        position_extra = position.get("extra", {})
        if not isinstance(position_extra, dict):
            return None
        base_size = position_extra.get("base_size")
        if base_size in (None, ""):
            return None
        return Decimal(str(base_size))

    def _emit_tp_sl_deferred_warning(self, *, pair: str, reason: str) -> None:
        """Emit one consistent warning when deferred TP/SL could not complete."""
        self.message_bus.send_message.emit(
            UserMessage(
                text=f"Order created for {pair}, but {reason}",
                level=MessageLevel.WARNING,
                timeout_ms=5000,
            ),
        )

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
            if order_data[
                "order_type"
            ].is_regular_order and self._should_replace_regular_order_on_edit_failure(error):
                try:
                    await self._replace_regular_order(order_data, trade_arguments)
                except TransactionFailedError as replace_error:
                    self.message_bus.send_message.emit(
                        UserMessage(
                            text=f"Failed to edit order: {replace_error}",
                            level=MessageLevel.ERROR,
                            timeout_ms=5000,
                        ),
                    )
                    return
            else:
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

    async def _replace_regular_order(
        self,
        order_data: OrderData,
        trade_arguments: dict[str, object],
    ) -> None:
        """Replace one regular order when native edit fails in practice."""
        await self.trader.cancel_order(
            {
                "order_id": self._cancel_order_id(order_data),
                "symbol": self._symbol_from_order(order_data),
                "trade_type": order_data["order_type"],
            },
        )
        create_arguments = dict(trade_arguments)
        create_arguments.pop("order_id", None)
        await self.trader.create_order(create_arguments)

    @staticmethod
    def _should_replace_regular_order_on_edit_failure(error: TransactionFailedError) -> bool:
        """Return whether a failed regular-order edit should fall back to cancel plus create."""
        error_text = str(error)
        return not any(
            marker in error_text for marker in ("[429]", "[401]", "[403]", "[500]", "timeout")
        )

    @asyncSlot()
    async def create_reduce_order(
        self,
        pair: str,
        size: Decimal,
        collateral_delta: Decimal,  # noqa: ARG002
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Decimal | None,
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

        await self._refresh_after_order_submission(pair=pair, refresh_positions=False)

    async def submit_position_tp_sl(
        self,
        *,
        pair: str,
        size_stable: Decimal,
        trade_direction: PerpsTradeDirection,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
        reference_price: Decimal,
        base_size: Decimal | None = None,
    ) -> None:
        """Create or edit native positional TP/SL protection through core exchange logic."""
        if take_profit_price is None and stop_loss_price is None:
            return

        existing_order = self.fetcher.get_open_positional_tp_sl_order(
            pair=pair,
            trade_direction=trade_direction,
        )
        resolved_take_profit, resolved_stop_loss = self._merge_position_tp_sl_targets(
            existing_order=existing_order,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
        )
        trade_arguments = self._build_position_tp_sl_trade_arguments(
            pair=pair,
            size_stable=size_stable,
            trade_direction=trade_direction,
            take_profit_price=resolved_take_profit,
            stop_loss_price=resolved_stop_loss,
            reference_price=reference_price,
            base_size=base_size,
            existing_order=existing_order,
        )

        action = "create"
        try:
            if existing_order is None:
                await self.trader.create_reduce_order(trade_arguments)
            elif self._requires_positional_tp_sl_recreate(
                existing_order=existing_order,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
            ):
                await self._replace_position_tp_sl_order(
                    existing_order=existing_order,
                    trade_arguments=self._build_position_tp_sl_trade_arguments(
                        pair=pair,
                        size_stable=size_stable,
                        trade_direction=trade_direction,
                        take_profit_price=resolved_take_profit,
                        stop_loss_price=resolved_stop_loss,
                        reference_price=reference_price,
                        base_size=base_size,
                        existing_order=None,
                    ),
                )
                action = "update"
            else:
                await self.trader.edit_order(trade_arguments)
                action = "update"
            self.message_bus.send_message.emit(
                UserMessage(
                    text=self._tp_sl_submission_message(
                        pair=pair,
                        take_profit_price=take_profit_price,
                        stop_loss_price=stop_loss_price,
                        action=action,
                    ),
                    level=MessageLevel.INFO,
                    timeout_ms=5000,
                ),
            )
        except TransactionFailedError as error:
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Failed to {action} reduce order: {error}",
                    level=MessageLevel.ERROR,
                    timeout_ms=5000,
                ),
            )
            return

        try:
            await asyncio.gather(
                self.fetcher.fetch_all_orders(), self.fetcher.fetch_all_positions()
            )
            self.message_bus.orders_fetched.emit(self.fetcher._cached_orders)  # noqa: SLF001
            self.message_bus.positions_fetched.emit(self.fetcher._cached_positions)  # noqa: SLF001
        except Exception as error:
            LOGGER.exception("Failed to refresh Orderly state after submitting position TP/SL")
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Created TP/SL order, but failed to refresh Orderly data: {error}",
                    level=MessageLevel.WARNING,
                    timeout_ms=5000,
                ),
            )

    async def _replace_position_tp_sl_order(
        self,
        *,
        existing_order: OrderData,
        trade_arguments: dict[str, object],
    ) -> None:
        """Replace one positional TP/SL root when Orderly cannot add a sibling by PUT."""
        await self.trader.cancel_order(
            {
                "order_id": self._native_order_id(existing_order),
                "symbol": self._symbol_from_order(existing_order),
                "trade_type": existing_order["order_type"],
            },
        )
        await self.trader.create_reduce_order(trade_arguments)

    async def _refresh_after_order_submission(self, *, pair: str, refresh_positions: bool) -> None:
        """Refresh order state after a successful Orderly order mutation."""
        try:
            if refresh_positions:
                await asyncio.gather(
                    self.fetcher.fetch_all_orders(), self.fetcher.fetch_all_positions()
                )
                self.message_bus.positions_fetched.emit(self.fetcher._cached_positions)  # noqa: SLF001
            else:
                await self.fetcher.fetch_all_orders()
            self.message_bus.orders_fetched.emit(self.fetcher._cached_orders)  # noqa: SLF001
        except Exception as error:
            LOGGER.exception("Failed to refresh Orderly state after submitting order for %s", pair)
            self.message_bus.send_message.emit(
                UserMessage(
                    text=f"Order submitted for {pair}, but failed to refresh Orderly data: {error}",
                    level=MessageLevel.WARNING,
                    timeout_ms=5000,
                ),
            )

    @asyncSlot()
    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel one open order."""
        if order_data["order_type"].is_tp_sl_order:
            try:
                await self._cancel_tp_sl_order_preserving_sibling(order_data)
            except TransactionFailedError as error:
                self.message_bus.send_message.emit(
                    UserMessage(
                        text=f"Failed to cancel order: {error}",
                        level=MessageLevel.ERROR,
                        timeout_ms=5000,
                    ),
                )
                return

            await self._refresh_after_order_submission(
                pair=order_data["pair"],
                refresh_positions=False,
            )
            return

        symbol = self._symbol_from_order(order_data)
        cancel_arguments = {
            "order_id": self._cancel_order_id(order_data),
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

        await self._refresh_after_order_submission(pair=order_data["pair"], refresh_positions=False)

    async def _cancel_tp_sl_order_preserving_sibling(self, order_data: OrderData) -> None:
        """Cancel TP/SL root and recreate surviving sibling leg when needed."""
        sibling_order = self._tp_sl_surviving_sibling(order_data)
        await self.trader.cancel_order(
            {
                "order_id": self._native_order_id(order_data),
                "symbol": self._symbol_from_order(order_data),
                "trade_type": order_data["order_type"],
            },
        )
        if sibling_order is None:
            return

        take_profit_price, stop_loss_price = self._surviving_tp_sl_targets(sibling_order)
        await self.trader.create_reduce_order(
            self._build_position_tp_sl_trade_arguments(
                pair=sibling_order["pair"],
                size_stable=sibling_order["size_stable"],
                trade_direction=sibling_order["trade_direction"],
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price,
                reference_price=sibling_order["trigger_price"],
                base_size=self._tp_sl_order_base_size(sibling_order),
                existing_order=None,
            ),
        )

    @staticmethod
    def _surviving_tp_sl_targets(order_data: OrderData) -> tuple[Decimal, Decimal]:
        """Return only the surviving TP or SL trigger for root recreation after delete."""
        if order_data["order_type"] is PerpsTradeType.TRIGGER_TP:
            return order_data["trigger_price"], Decimal(0)
        if order_data["order_type"] is PerpsTradeType.TRIGGER_SL:
            return Decimal(0), order_data["trigger_price"]
        return Decimal(0), Decimal(0)

    def _tp_sl_order_base_size(self, order_data: OrderData) -> Decimal | None:
        """Return preserved native base size for TP/SL recreate flows."""
        order_extra = order_data.get("extra", {})
        if isinstance(order_extra, dict):
            base_size = self._parse_positive_decimal(order_extra.get("base_size"))
            if base_size is not None:
                return base_size

        for position in getattr(self.fetcher, "_cached_positions", []):
            if (
                position["pair"] == order_data["pair"]
                and position["trade_direction"] is order_data["trade_direction"]
            ):
                position_extra = position.get("extra", {})
                if not isinstance(position_extra, dict):
                    continue
                base_size = self._parse_positive_decimal(position_extra.get("base_size"))
                if base_size is not None:
                    return base_size
        return None

    @staticmethod
    def _parse_positive_decimal(value: object) -> Decimal | None:
        """Return positive decimals only, treating zero-like values as missing."""
        if value in (None, ""):
            return None
        parsed = Decimal(str(value))
        if parsed <= Decimal(0):
            return None
        return parsed

    def _tp_sl_surviving_sibling(self, order_data: OrderData) -> OrderData | None:
        """Return sibling TP/SL order that should survive a clicked child cancel."""
        sibling_orders = [
            candidate
            for candidate in self._tp_sl_sibling_orders(order_data)
            if candidate["id"] != order_data["id"]
        ]
        if not sibling_orders:
            return None
        return sibling_orders[0]

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
        execution_price: Decimal | None,
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
            return 100
        max_leverage = payload.get("data", {}).get("max_leverage")
        if isinstance(max_leverage, int):
            return max_leverage
        if isinstance(max_leverage, str) and max_leverage:
            return int(max_leverage)
        return 100

    def _resolve_attached_tp_sl_targets(
        self,
        *,
        execution_price: Decimal,
        trade_direction: PerpsTradeDirection,
        take_profit: float | None,
        stop_loss: float | None,
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
            if self.app_config.stop_loss != 0:
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
            "order_id": self._native_order_id(order_data),
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
        order_extra = order_data.get("extra", {})
        if isinstance(order_extra, dict):
            root_algo_type = order_extra.get("root_algo_type")
            if root_algo_type not in (None, ""):
                trade_arguments["root_algo_type"] = str(root_algo_type)

        take_profit, stop_loss = self._tp_sl_targets_for_edit(
            order_data=order_data,
            edited_trigger_price=new_execution_price,
        )
        trade_arguments["take_profit"] = take_profit
        trade_arguments["stop_loss"] = stop_loss
        trade_arguments.update(self._tp_sl_child_order_ids(order_data))
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

    def _build_position_tp_sl_trade_arguments(
        self,
        *,
        pair: str,
        size_stable: Decimal,
        trade_direction: PerpsTradeDirection,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
        reference_price: Decimal,
        base_size: Decimal | None,
        existing_order: OrderData | None,
    ) -> dict[str, object]:
        """Build native trade arguments for positional TP/SL create or edit flows."""
        resolved_take_profit, resolved_stop_loss = self._merge_position_tp_sl_targets(
            existing_order=existing_order,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
        )
        trade_arguments: dict[str, object] = {
            "symbol": self._market_registry.get_symbol_for_pair(pair),
            "trade_direction": trade_direction,
            "trade_type": (
                PerpsTradeType.TRIGGER_TP
                if resolved_take_profit != Decimal(0)
                else PerpsTradeType.TRIGGER_SL
            ),
            "price": reference_price,
            "size_stable": size_stable,
            "reduce_only": True,
            "take_profit": resolved_take_profit,
            "stop_loss": resolved_stop_loss,
        }
        if base_size is not None:
            trade_arguments["base_size"] = base_size
        if existing_order is None:
            return trade_arguments

        trade_arguments["order_id"] = self._native_order_id(existing_order)
        order_extra = existing_order.get("extra", {})
        if isinstance(order_extra, dict):
            root_algo_type = order_extra.get("root_algo_type")
            if root_algo_type not in (None, ""):
                trade_arguments["root_algo_type"] = str(root_algo_type)
        trade_arguments.update(self._tp_sl_child_order_ids(existing_order))
        return trade_arguments

    def _merge_position_tp_sl_targets(
        self,
        *,
        existing_order: OrderData | None,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> tuple[Decimal, Decimal]:
        """Merge requested TP/SL values with cached existing positional protection."""
        if existing_order is None:
            return take_profit_price or Decimal(0), stop_loss_price or Decimal(0)

        current_take_profit, current_stop_loss = self._tp_sl_targets_for_edit(
            order_data=existing_order,
            edited_trigger_price=existing_order["trigger_price"],
        )
        return (
            take_profit_price if take_profit_price is not None else current_take_profit,
            stop_loss_price if stop_loss_price is not None else current_stop_loss,
        )

    def _requires_positional_tp_sl_recreate(
        self,
        *,
        existing_order: OrderData,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> bool:
        """Return whether Orderly requires cancel+create to add a missing sibling leg."""
        current_take_profit, current_stop_loss = self._tp_sl_targets_for_edit(
            order_data=existing_order,
            edited_trigger_price=existing_order["trigger_price"],
        )
        return (current_take_profit == Decimal(0) and take_profit_price is not None) or (
            current_stop_loss == Decimal(0) and stop_loss_price is not None
        )

    def _tp_sl_child_order_ids(self, order_data: OrderData) -> dict[str, str]:
        """Return existing TP/SL child ids keyed by leg for native edit payloads."""
        child_order_ids: dict[str, str] = {}
        for candidate in self._tp_sl_sibling_orders(order_data):
            child_id = str(candidate["id"]).strip()
            if child_id in {"", "0"}:
                continue
            if candidate["order_type"] is PerpsTradeType.TRIGGER_TP:
                child_order_ids["tp_child_order_id"] = child_id
            elif candidate["order_type"] is PerpsTradeType.TRIGGER_SL:
                child_order_ids["sl_child_order_id"] = child_id
        return child_order_ids

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
    def _native_order_id(order_data: OrderData) -> str:
        """Return the native Orderly order identifier used for edits and cancels."""
        root_algo_order_id = OrderlyExchange._root_algo_order_id(order_data)
        if order_data["order_type"].is_tp_sl_order and root_algo_order_id is not None:
            return root_algo_order_id
        order_extra = order_data.get("extra", {})
        if isinstance(order_extra, dict):
            native_order_id = order_extra.get("native_order_id")
            if native_order_id not in (None, ""):
                return str(native_order_id)
        return str(order_data["id"])

    @staticmethod
    def _cancel_order_id(order_data: OrderData) -> str:
        """Return native Orderly identifier used for one-click cancellation."""
        order_extra = order_data.get("extra", {})
        if isinstance(order_extra, dict):
            native_algo_order_id = order_extra.get("algo_order_id")
            if native_algo_order_id not in (None, "", "0"):
                return str(native_algo_order_id)
            native_order_id = order_extra.get("native_order_id")
            if native_order_id not in (None, ""):
                return str(native_order_id)
        return str(order_data["id"])

    @staticmethod
    def _tp_sl_submission_message(
        *,
        pair: str,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
        action: str,
    ) -> str:
        """Build user-facing message for positional TP/SL create or update flows."""
        verb = "Updating" if action == "update" else "Creating"
        if take_profit_price is not None and stop_loss_price is not None:
            return f"{verb} TP and SL order for {pair}"
        if take_profit_price is not None:
            return f"{verb} take-profit order for {pair}"
        return f"{verb} stop-loss order for {pair}"

    @staticmethod
    def name() -> str:
        """Return exchange identifier."""
        return "orderly"

    @staticmethod
    def new_account_info() -> NewAccountInfo:
        """Provide required secrets for account creation dialog."""
        return {
            "referral_link": None,
            "fields": [
                {"label": "Orderly Account ID"},
                {"label": "Orderly API Key (orderly-key)"},
                {"label": "Orderly Secret"},
                {
                    "label": "Network",
                    "field_type": "select",
                    "options": [
                        {"label": "Mainnet", "value": OrderlyNetwork.MAINNET.value},
                        {"label": "Testnet", "value": OrderlyNetwork.TESTNET.value},
                    ],
                },
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


def _extract_source_order_id(result: object) -> str | None:
    """Return native Orderly order id from create-order response when present."""
    if not isinstance(result, dict):
        return None
    order_id = result.get("order_id")
    if order_id in (None, ""):
        return None
    return str(order_id)


def _normalize_orderly_key(orderly_key: str) -> str:
    """Normalize API key to include required Orderly prefix."""
    normalized_key = orderly_key.strip()
    if normalized_key.startswith(_ORDERLY_KEY_PREFIX):
        return normalized_key
    return f"{_ORDERLY_KEY_PREFIX}{normalized_key}"


def _extract_max_leverage_from_error(error: TransactionFailedError) -> int | None:
    """Extract the server-reported max leverage from an Orderly error message."""
    match = _LEVERAGE_RANGE_PATTERN.search(str(error))
    if match is None:
        return None
    return int(match.group(2))
