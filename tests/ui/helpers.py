"""Shared helpers for UI-focused tests."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from types import SimpleNamespace
from typing import Any, ClassVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas
from PySide6 import QtCore, QtWidgets

from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType


def ensure_app() -> QtWidgets.QApplication:
    """Return the shared QApplication instance."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def process_events() -> None:
    """Process pending Qt events."""
    ensure_app().processEvents()


def run_async(bound_method: object, *args: object, **kwargs: object) -> object:
    """Run a coroutine or qasync-wrapped bound method synchronously in tests."""
    wrapped = getattr(bound_method, "__wrapped__", None)
    if wrapped is not None and getattr(bound_method, "__self__", None) is not None:
        owner = bound_method.__self__
        return asyncio.run(wrapped(owner, *args, **kwargs))
    if callable(bound_method):
        return asyncio.run(bound_method(*args, **kwargs))
    msg = "bound_method must be callable"
    raise TypeError(msg)


def create_closed_task(coroutine: object) -> QtCore.QObject:
    """Close one created coroutine and return a lightweight task double."""
    close = getattr(coroutine, "close", None)
    if callable(close):
        close()
    return QtCore.QObject()


class MessageBusStub(QtCore.QObject):
    """Minimal message bus stub exposing the app signal surface."""

    subscribed_prices_fetched = QtCore.Signal(object)
    balance_fetched = QtCore.Signal(object)
    positions_fetched = QtCore.Signal(object)
    orders_fetched = QtCore.Signal(object)
    raw_news = QtCore.Signal(object)
    formatted_news = QtCore.Signal(object)
    formatted_news_updated = QtCore.Signal(object)
    send_message = QtCore.Signal(object)


class AppConfigStub(QtCore.QObject):
    """App-config stub with the signals and settings used by widgets."""

    LEVERAGE_BUTTON_FIELDS = (
        "leverage_button_1",
        "leverage_button_2",
        "leverage_button_3",
        "leverage_button_4",
        "leverage_button_5",
        "leverage_button_6",
        "leverage_button_7",
    )

    leverage_changed = QtCore.Signal(int)
    stop_loss_changed = QtCore.Signal(float)
    take_profit_changed = QtCore.Signal(float)
    trade_value_lowest_changed = QtCore.Signal(int)
    trade_value_low_changed = QtCore.Signal(int)
    trade_value_medium_changed = QtCore.Signal(int)
    trade_value_high_changed = QtCore.Signal(int)
    leverage_button_1_changed = QtCore.Signal(int)
    leverage_button_2_changed = QtCore.Signal(int)
    leverage_button_3_changed = QtCore.Signal(int)
    leverage_button_4_changed = QtCore.Signal(int)
    leverage_button_5_changed = QtCore.Signal(int)
    leverage_button_6_changed = QtCore.Signal(int)
    leverage_button_7_changed = QtCore.Signal(int)
    current_account_id_changed = QtCore.Signal(int)
    news_show_images_changed = QtCore.Signal(bool)
    news_desktop_notifications_changed = QtCore.Signal(bool)
    minimize_to_tray_changed = QtCore.Signal(bool)
    window_geometry_changed = QtCore.Signal(str)
    toast_message_position_changed = QtCore.Signal(str)
    toast_widget_position_changed = QtCore.Signal(str)
    toast_message_duration_changed = QtCore.Signal(int)
    toast_widget_duration_changed = QtCore.Signal(int)
    account_deleted = QtCore.Signal()
    account_created = QtCore.Signal()

    DEFAULT_GUI_SETTINGS: ClassVar[dict[str, object]] = {
        "news_show_images": True,
        "news_desktop_notifications": True,
        "minimize_to_tray": True,
        "toast_message_position": "bottom_left",
        "toast_widget_position": "bottom_left",
        "toast_message_duration": 10,
        "toast_widget_duration": 35,
        "window_geometry": "",
    }

    TRADE_DEFAULTS: ClassVar[dict[str, object]] = {
        "take_profit": 0.0,
        "stop_loss": 0.0,
        "trade_value_lowest": 100,
        "trade_value_low": 250,
        "trade_value_medium": 500,
        "trade_value_high": 1000,
        "leverage": 10,
        "leverage_button_1": 2,
        "leverage_button_2": 5,
        "leverage_button_3": 10,
        "leverage_button_4": 20,
        "leverage_button_5": 25,
        "leverage_button_6": 50,
        "leverage_button_7": 100,
    }

    def __init__(self) -> None:
        """Initialize mutable config state."""
        super().__init__()
        self.take_profit = 1.5
        self.stop_loss = 0.75
        self.trade_value_lowest = 10
        self.trade_value_low = 25
        self.trade_value_medium = 50
        self.trade_value_high = 100
        self.leverage_button_1 = 2
        self.leverage_button_2 = 5
        self.leverage_button_3 = 10
        self.leverage_button_4 = 20
        self.leverage_button_5 = 25
        self.leverage_button_6 = 50
        self.leverage_button_7 = 100
        self.leverage = 5
        self.current_account_id = 1
        self._settings = {
            "news_show_images": True,
            "news_desktop_notifications": False,
            "minimize_to_tray": True,
            "toast_message_position": "top_right",
            "toast_widget_position": "bottom_left",
            "toast_message_duration": 12,
            "toast_widget_duration": 33,
            "window_geometry": "",
        }
        self._settings_imports: list[dict[str, object]] = []
        self._accounts = [
            SimpleNamespace(
                id=1,
                get_id=lambda: 1,
                username="demo_account",
                exchange_name="orderly",
                exchange_type=0,
            )
        ]
        self.current_keyring_account = self._accounts[0]

    def get_gui_settings(self, key: str) -> object:
        """Return one stored GUI setting."""
        return self._settings[key]

    def set_gui_settings(self, key: str, value: object) -> None:
        """Store one GUI setting and emit its change signal when present."""
        self._settings[key] = value
        signal = getattr(self, f"{key}_changed", None)
        if signal is not None:
            signal.emit(value)

    def get_all_accounts(self) -> list[SimpleNamespace]:
        """Return the current account list."""
        return list(self._accounts)

    def create_account(
        self,
        *,
        username: str,
        exchange_type: object,
        exchange_name: str,
    ) -> SimpleNamespace:
        """Create and select a new in-memory account."""
        account_id = len(self._accounts) + 1
        account = SimpleNamespace(
            id=account_id,
            get_id=lambda account_id=account_id: account_id,
            username=username,
            exchange_name=exchange_name,
            exchange_type=exchange_type,
        )
        self._accounts.append(account)
        self.current_keyring_account = account
        self.account_created.emit()
        return account

    def delete_account(self, account_id: int) -> None:
        """Delete one in-memory account."""
        self._accounts = [account for account in self._accounts if account.id != account_id]
        self.account_deleted.emit()

    def load_all_configs(self) -> None:
        """Match the production config API."""

    def reset_current_trade_config(self) -> None:
        """Reset the in-memory trade settings to defaults."""
        for field_name, value in self.TRADE_DEFAULTS.items():
            setattr(self, field_name, value)

    def reset_terminal_gui_settings(self) -> None:
        """Reset the terminal-facing GUI settings to defaults."""
        for key in (
            "news_show_images",
            "news_desktop_notifications",
            "minimize_to_tray",
        ):
            value = self.DEFAULT_GUI_SETTINGS[key]
            self.set_gui_settings(key, value)

    def reset_toast_gui_settings(self) -> None:
        """Reset the toast settings to defaults."""
        for key in (
            "toast_message_position",
            "toast_widget_position",
            "toast_message_duration",
            "toast_widget_duration",
        ):
            value = self.DEFAULT_GUI_SETTINGS[key]
            self.set_gui_settings(key, value)

    def export_settings_snapshot(self) -> dict[str, object]:
        """Return a stable settings snapshot."""
        return {
            "version": 1,
            "gui_settings": {
                key: self._settings[key]
                for key in (
                    "news_show_images",
                    "news_desktop_notifications",
                    "minimize_to_tray",
                    "toast_message_position",
                    "toast_widget_position",
                    "toast_message_duration",
                    "toast_widget_duration",
                )
            },
            "trade_config": {
                field_name: getattr(self, field_name)
                for field_name in (
                    "leverage",
                    "take_profit",
                    "stop_loss",
                    "trade_value_lowest",
                    "trade_value_low",
                    "trade_value_medium",
                    "trade_value_high",
                    *self.LEVERAGE_BUTTON_FIELDS,
                )
            },
            "user_filters": [],
        }

    def import_settings_snapshot(self, snapshot: dict[str, object]) -> list[str]:
        """Record and apply an imported settings snapshot."""
        self._settings_imports.append(deepcopy(snapshot))
        gui_settings = snapshot.get("gui_settings", {})
        if isinstance(gui_settings, dict):
            for key, value in gui_settings.items():
                self.set_gui_settings(key, value)
        trade_config = snapshot.get("trade_config", {})
        if isinstance(trade_config, dict):
            for key, value in trade_config.items():
                setattr(self, key, value)
        return []

    @property
    def leverage_button_values(self) -> list[int]:
        """Return configured leverage preset button values."""
        return [getattr(self, field_name) for field_name in self.LEVERAGE_BUTTON_FIELDS]


class PassGuardStub:
    """Password-guard stub used by controller and dialog tests."""

    def __init__(self) -> None:
        """Initialize the mutable password holder."""
        self.password = ""

    def decrypt(self, value: str) -> str:
        """Match the production password-guard API."""
        return value


class FilterManagerStub:
    """Filter-manager stub tracking refresh requests."""

    def __init__(self) -> None:
        """Initialize the stub."""
        self.updated = False

    def update_filters(self) -> None:
        """Record a refresh request."""
        self.updated = True


class FetcherStub:
    """Exchange fetcher stub used by UI widgets."""

    def __init__(self, pair: str) -> None:
        """Initialize cached fetch state."""
        self.calls: list[tuple[str, object]] = []
        self._cached_orders: list[dict[str, object]] = []
        self._cached_positions: list[dict[str, object]] = []
        self._cached_prices: dict[str, dict[str, object]] = {
            pair: {"price": Decimal(100000), "date": datetime.now(timezone.utc)}
        }

    async def subscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Record one subscribe request."""
        self.calls.append(("subscribe", (pair, force)))

    async def unsubscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Record one unsubscribe request."""
        self.calls.append(("unsubscribe", (pair, force)))

    async def fetch_price_at_time(self, pair: str, _timestamp: float) -> dict[str, Decimal]:
        """Return a stable historical price."""
        price = self._cached_prices[pair]["price"]
        return {"price": price if isinstance(price, Decimal) else Decimal(str(price))}

    async def fetch_current_price(self, pair: str) -> dict[str, Decimal]:
        """Return the latest cached price."""
        price = self._cached_prices[pair]["price"]
        return {"price": price if isinstance(price, Decimal) else Decimal(str(price))}

    @property
    def cached_prices(self) -> dict[str, dict[str, object]]:
        """Expose cached prices without private-member access in tests."""
        return self._cached_prices

    async def fetch_all_orders(self) -> list[dict[str, object]]:
        """Return cached orders."""
        return list(self._cached_orders)

    async def fetch_all_positions(self) -> list[dict[str, object]]:
        """Return cached positions."""
        return list(self._cached_positions)


class ExchangeStub(QtCore.QObject):
    """Exchange stub with the widget surface used across UI tests."""

    def __init__(self, pair: str = "Crypto.BTC/USDC") -> None:
        """Initialize exchange state."""
        super().__init__()
        self.message_bus = MessageBusStub()
        self.available_pairs = {pair, "Crypto.ETH/USDC"}
        self.default_pair = pair
        self.quote_symbol = "USDC"
        self.max_leverage = 100
        self.min_leverage = 1
        self._pair_max_leverage = {
            "Crypto.BTC/USDC": 25,
            "Crypto.ETH/USDC": 50,
        }
        self.pair_prefix = "Crypto."
        self.pair_separator = "/"
        self.pair_suffix = ""
        self.fetcher = FetcherStub(pair)
        self.cached_prices = self.fetcher.cached_prices
        self.stable_balance = Decimal(200)
        self.account_info = {
            "Available Balance + Unsettled PnL": Decimal(200),
            "Available Balance": Decimal(180),
            "Unsettled PnL": Decimal(20),
            "Free Balance": Decimal(150),
            "Account Id": "acct-123",
        }
        self.created_orders: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.reduce_orders: list[dict[str, object]] = []
        self.closed_positions: list[dict[str, object]] = []
        self.cancelled_orders: list[dict[str, object]] = []
        self.edited_orders: list[dict[str, object]] = []
        self._associated_position: dict[str, object] | None = None

    @staticmethod
    def name() -> str:
        """Return the exchange name."""
        return "orderly"

    def format_simple_pair_from_pair(self, pair: str) -> str:
        """Format an exchange pair for display."""
        return pair.replace("Crypto.", "")

    def format_coin_from_pair(self, pair: str) -> str:
        """Extract the base coin from a pair."""
        return self.format_simple_pair_from_pair(pair).split("/")[0]

    def format_pair_from_coin(self, coin: str) -> str:
        """Build one exchange pair from a coin."""
        return f"Crypto.{coin}/USDC"

    def max_leverage_for_pair(self, pair: str) -> int:
        """Return the configured leverage cap for one pair."""
        return self._pair_max_leverage.get(pair, self.max_leverage)

    def calculate_margin_fee(self, position_size: Decimal) -> Decimal:
        """Return a deterministic fee preview."""
        return position_size / Decimal(100)

    def calculate_liquidation_price(self, perps_position: dict[str, object]) -> Decimal:
        """Return a deterministic liquidation price."""
        open_price = Decimal(str(perps_position["open_price"]))
        if perps_position["trade_direction"] is PerpsTradeDirection.LONG:
            return open_price * Decimal("0.9")
        return open_price * Decimal("1.1")

    def use_native_position_pnl(self) -> bool:
        """Use price-based pnl in tests."""
        return False

    def calculate_pnl(
        self,
        _perps_position: dict[str, object],
        current_price: Decimal | None,
    ) -> dict[str, Decimal | bool | str]:
        """Return predictable pnl details."""
        price = current_price or Decimal(100)
        return {
            "pnl_usd_before_fees": price / Decimal(10),
            "pnl_percentage_before_fees": Decimal(5),
            "funding_fee_usd": Decimal(1),
            "opening_fee_usd": Decimal(2),
            "closing_fee_usd": Decimal(3),
            "pnl_usd_after_fees": price / Decimal(12),
            "pnl_percentage_after_fees": Decimal(4),
            "pnl_label": "Unrealized PnL",
            "net_pnl_label": "Close-now PnL",
            "show_closing_fee": True,
        }

    async def create_order(self, *args: object, **kwargs: object) -> None:
        """Record one create-order request."""
        self.created_orders.append((args, dict(kwargs)))

    async def create_reduce_order(self, **kwargs: object) -> None:
        """Record one reduce-order request."""
        self.reduce_orders.append(dict(kwargs))

    async def close_position(self, position: dict[str, object]) -> None:
        """Record one close-position request."""
        self.closed_positions.append(position)

    async def cancel_order(self, order_data: dict[str, object]) -> None:
        """Record one cancel-order request."""
        self.cancelled_orders.append(order_data)

    async def edit_order(
        self,
        *,
        order_data: dict[str, object],
        new_size_stable: Decimal,
        new_execution_price: Decimal,
    ) -> None:
        """Record one edit-order request."""
        self.edited_orders.append(
            {
                "order_data": order_data,
                "new_size_stable": new_size_stable,
                "new_execution_price": new_execution_price,
            }
        )

    async def set_leverage(self, _coin: str, _leverage: int) -> None:
        """Match the exchange API used by widgets."""

    async def set_all_leverage(self, _leverage: int) -> None:
        """Match the exchange API used by widgets."""

    async def is_ready_to_trade(self) -> bool:
        """Keep account-info tests simple."""
        return True

    async def approve_for_trading(self) -> None:
        """Match the account-info widget contract."""

    def get_position_associated_with_order(
        self,
        _order_data: dict[str, object],
    ) -> dict[str, object] | None:
        """Return the preconfigured associated position."""
        return self._associated_position


class NewsManagerStub:
    """News-manager stub returning pre-seeded news items."""

    def __init__(self, news_items: list[dict[str, object]] | None = None) -> None:
        """Store seeded news data."""
        self.news_items = list(news_items or [])
        self.restarts = 0

    async def fetch_old_news(self, max_news: int) -> list[dict[str, object]]:
        """Return the latest seeded news items."""
        return list(self.news_items[:max_news])

    async def fetch_news(self) -> None:
        """Match the production async API."""

    async def stop_async(self) -> None:
        """Match the production async API."""


class UIControllerStub(QtCore.QObject):
    """UI controller stub shared by widget and window tests."""

    exchange_changed = QtCore.Signal()
    pair_changed = QtCore.Signal(str)
    timeframe_changed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        exchange: ExchangeStub | None = None,
        app_config: AppConfigStub | None = None,
        message_bus: MessageBusStub | None = None,
        news_items: list[dict[str, object]] | None = None,
    ) -> None:
        """Initialize a reusable UI controller stub."""
        super().__init__()
        self.current_exchange = exchange or ExchangeStub()
        self.app_config = app_config or AppConfigStub()
        self.message_bus = message_bus or MessageBusStub()
        self.pass_guard = PassGuardStub()
        self.news_filter_manager = FilterManagerStub()
        self.news_manager = NewsManagerStub(news_items)
        self.current_pair = self.current_exchange.default_pair
        self.current_timeframe = "1"
        self.changed_pairs: list[str] = []
        self.submitted_tp_sl: list[dict[str, object]] = []
        self.news_manager_restarts = 0

    @property
    def exchange_available_pairs(self) -> set[str]:
        """Expose exchange pairs for the search modal."""
        return self.current_exchange.available_pairs

    async def change_current_pair(self, pair: str) -> None:
        """Update the current pair and notify listeners."""
        self.current_pair = pair
        self.changed_pairs.append(pair)
        self.pair_changed.emit(pair)

    async def set_leverage(self, _coin: str, leverage: int) -> None:
        """Mirror leverage changes to app config."""
        self.app_config.leverage = leverage
        self.app_config.leverage_changed.emit(leverage)

    async def set_all_leverage(self, leverage: int) -> None:
        """Mirror bulk leverage changes to app config."""
        await self.set_leverage("BTC", leverage)

    async def change_timeframe(self, resolution: str) -> None:
        """Update the active timeframe."""
        self.current_timeframe = resolution
        self.timeframe_changed.emit(resolution)

    async def fetch_price_history(self) -> tuple[pandas.DataFrame, int]:
        """Return a small deterministic candle history."""
        return build_price_history(), 2

    async def fetch_price_history_for_timeframe(self, _resolution: str) -> pandas.DataFrame:
        """Return a small deterministic candle history."""
        return build_price_history()

    def format_simple_pair_from_pair(self, pair: str) -> str:
        """Delegate pair formatting to the exchange."""
        return self.current_exchange.format_simple_pair_from_pair(pair)

    async def submit_position_tp_sl(self, order_request: dict[str, object]) -> None:
        """Record TP/SL requests forwarded by action cells."""
        self.submitted_tp_sl.append(order_request)

    async def restart_news_manager(self) -> None:
        """Record restart requests from news config."""
        self.news_manager_restarts += 1

    def update_news_filters(self) -> None:
        """Record filter refresh requests."""
        self.news_filter_manager.update_filters()


def build_price_history() -> pandas.DataFrame:
    """Create deterministic OHLCV history for chart tests."""
    now = datetime.now(timezone.utc)
    return pandas.DataFrame(
        {
            "date": [now - timedelta(minutes=2), now - timedelta(minutes=1)],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1.0, 1.5],
        }
    )


def build_news_data(
    *,
    news_id: str = "news-1",
    title: str = "BTC moves",
    coin: set[str] | None = None,
    ignored: bool = False,
    is_update: bool = False,
    applied_updates: set[str] | None = None,
) -> dict[str, object]:
    """Create minimal news data for widget tests."""
    return {
        "news_id": news_id,
        "title": title,
        "link": QtCore.QUrl("https://example.com"),
        "body": "body",
        "image": "",
        "is_quote": False,
        "quote_message": "",
        "quote_user": "",
        "quote_image": "",
        "is_reply": False,
        "is_self_reply": False,
        "reply_user": "",
        "reply_message": "",
        "reply_image": "",
        "is_retweet": False,
        "retweet_user": "",
        "icon": "",
        "source": "webs",
        "time": datetime.now(timezone.utc) - timedelta(minutes=2),
        "coin": coin or {"BTC"},
        "feed": "Feed",
        "sfx": ":/sfx/test",
        "is_update": is_update,
        "update_type": "",
        "applied_updates": applied_updates or set(),
        "summary_title": "",
        "summary_body": "",
        "is_important": False,
        "ignored": ignored,
    }


def build_position(
    *,
    pair: str = "Crypto.BTC/USDC",
    trade_direction: PerpsTradeDirection = PerpsTradeDirection.LONG,
) -> dict[str, object]:
    """Create one deterministic perps position payload."""
    return {
        "pair": pair,
        "id": 1,
        "position_size_stable": Decimal(100),
        "collateral_stable": Decimal(20),
        "open_price": Decimal(100000),
        "trade_direction": trade_direction,
        "leverage": Decimal(5),
        "liquidation_price": Decimal(90000),
        "extra": {"base_size": Decimal("0.001")},
    }


def build_order(
    *,
    order_id: str = "order-1",
    pair: str = "Crypto.BTC/USDC",
    trade_direction: PerpsTradeDirection = PerpsTradeDirection.LONG,
    order_type: PerpsTradeType = PerpsTradeType.LIMIT,
    reduce_only: bool = False,
    trigger_price: Decimal = Decimal(100000),
    size_stable: Decimal = Decimal(50),
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Create one deterministic order payload."""
    return {
        "id": order_id,
        "pair": pair,
        "trigger_price": trigger_price,
        "size_stable": size_stable,
        "trade_direction": trade_direction,
        "order_type": order_type,
        "reduce_only": reduce_only,
        "extra": extra or {},
    }
