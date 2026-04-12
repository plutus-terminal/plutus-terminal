# ruff: noqa: S101, SLF001

"""Focused parity tests for the Orderly trade widget."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, ClassVar
import unittest
from unittest.mock import AsyncMock

from PySide6 import QtCore, QtWidgets

from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType
from plutus_terminal.ui.widgets.perps_trade import PerpsTradeWidget

_BTC_PAIR_MAX_LEVERAGE = 25
_ETH_PAIR_MAX_LEVERAGE = 50


class _MessageBus(QtCore.QObject):
    """Minimal signal-only message bus for widget tests."""

    subscribed_prices_fetched = QtCore.Signal(object)
    balance_fetched = QtCore.Signal(object)


class _AppConfig(QtCore.QObject):
    """Minimal app config exposing the widget signal contract."""

    trade_value_high_changed = QtCore.Signal()
    trade_value_low_changed = QtCore.Signal()
    trade_value_medium_changed = QtCore.Signal()
    trade_value_lowest_changed = QtCore.Signal()
    leverage_button_1_changed = QtCore.Signal(int)
    leverage_button_2_changed = QtCore.Signal(int)
    leverage_button_3_changed = QtCore.Signal(int)
    leverage_button_4_changed = QtCore.Signal(int)
    leverage_button_5_changed = QtCore.Signal(int)
    leverage_button_6_changed = QtCore.Signal(int)
    leverage_button_7_changed = QtCore.Signal(int)
    leverage_changed = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.trade_value_lowest = Decimal(10)
        self.trade_value_low = Decimal(25)
        self.trade_value_medium = Decimal(50)
        self.trade_value_high = Decimal(100)
        self.leverage_button_1 = 2
        self.leverage_button_2 = 5
        self.leverage_button_3 = 10
        self.leverage_button_4 = 20
        self.leverage_button_5 = 25
        self.leverage_button_6 = 50
        self.leverage_button_7 = 100
        self.leverage = 5

    @property
    def leverage_button_values(self) -> list[int]:
        return [
            self.leverage_button_1,
            self.leverage_button_2,
            self.leverage_button_3,
            self.leverage_button_4,
            self.leverage_button_5,
            self.leverage_button_6,
            self.leverage_button_7,
        ]


class _ExchangeStub:
    """Minimal exchange surface consumed by PerpsTradeWidget."""

    quote_symbol: ClassVar[str] = "USDC"
    min_leverage: ClassVar[int] = 1
    max_leverage: ClassVar[int] = 100
    available_pairs: ClassVar[set[str]] = {"Crypto.BTC/USDC", "Crypto.ETH/USDC"}
    default_pair: ClassVar[str] = "Crypto.BTC/USDC"
    pair_prefix: ClassVar[str] = "Crypto."
    pair_suffix: ClassVar[str] = ""
    pair_separator: ClassVar[str] = "/"
    pair_max_leverage: ClassVar[dict[str, int]] = {
        "Crypto.BTC/USDC": _BTC_PAIR_MAX_LEVERAGE,
        "Crypto.ETH/USDC": _ETH_PAIR_MAX_LEVERAGE,
    }
    cached_prices: ClassVar[dict[str, dict[str, Decimal]]] = {
        "Crypto.BTC/USDC": {"price": Decimal(97500)},
        "Crypto.ETH/USDC": {"price": Decimal(3000)},
    }
    stable_balance: ClassVar[Decimal] = Decimal(100)

    @staticmethod
    def format_simple_pair_from_pair(pair: str) -> str:
        return pair.replace("Crypto.", "")

    @staticmethod
    def format_coin_from_pair(pair: str) -> str:
        return pair.replace("Crypto.", "").split("/")[0]

    @classmethod
    def max_leverage_for_pair(cls, pair: str) -> int:
        return cls.pair_max_leverage[pair]

    @staticmethod
    def calculate_margin_fee(_position_size: Decimal) -> Decimal:
        return Decimal(1)

    @staticmethod
    def calculate_liquidation_price(_position: object) -> Decimal:
        return Decimal(90000)


class _UIControllerStub(QtCore.QObject):
    """Minimal controller surface consumed by PerpsTradeWidget."""

    exchange_changed = QtCore.Signal()
    pair_changed = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_exchange = _ExchangeStub()
        self.app_config = _AppConfig()
        self.message_bus = _MessageBus()
        self.current_pair = "Crypto.BTC/USDC"

    async def change_current_pair(self, _pair: str) -> None:
        """Satisfy the widget callback contract."""

    async def set_leverage(self, _coin: str, _leverage: int) -> None:
        """Satisfy the widget callback contract."""


class OrderlyTradeWidgetParityTests(unittest.TestCase):
    """Verify missing trading-only Orderly flows stay reachable in the desktop UI."""

    @classmethod
    def setUpClass(cls) -> None:
        """Ensure one QApplication exists for widget tests."""
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_get_trade_type_returns_stop_market_for_stop_tab(self) -> None:
        """Expose stop-market entry from the main Perps trade widget."""
        # Arrange
        ui_controller: Any = _UIControllerStub()
        widget = PerpsTradeWidget(ui_controller)

        # Act
        widget._trade_tab.setCurrentWidget(widget._trade_type_stop)

        # Assert
        assert widget.get_trade_type() is PerpsTradeType.STOP_MARKET

    def test_limit_tab_submits_regular_limit_order_without_attached_tp_sl(self) -> None:
        """Keep the desktop limit-entry flow on the regular Orderly order path."""
        # Arrange
        ui_controller: Any = _UIControllerStub()
        ui_controller.current_exchange.create_order = AsyncMock()
        widget = PerpsTradeWidget(ui_controller)
        widget._trade_tab.setCurrentWidget(widget._trade_type_limit)
        widget._trade_type_limit.amount_box.setValue(Decimal(10))
        widget._trade_type_limit.target_price_box.setValue(Decimal("97500.5"))

        # Act
        event_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(event_loop)
            task = widget._create_order(PerpsTradeDirection.LONG)
            event_loop.run_until_complete(task)
        finally:
            asyncio.set_event_loop(None)
            event_loop.close()

        # Assert
        ui_controller.current_exchange.create_order.assert_awaited_once_with(
            "Crypto.BTC/USDC",
            Decimal(10),
            PerpsTradeDirection.LONG,
            PerpsTradeType.LIMIT,
            Decimal("97500.5"),
            0.0,
            0.0,
        )

    def test_pair_specific_leverage_cap_updates_when_selected_pair_changes(self) -> None:
        """Refresh the leverage spin cap from the selected Orderly market metadata."""
        # Arrange
        ui_controller: Any = _UIControllerStub()
        ui_controller.set_leverage = AsyncMock()
        widget = PerpsTradeWidget(ui_controller)

        # Assert initial pair cap
        assert widget._leverage_spin.maximum() == _BTC_PAIR_MAX_LEVERAGE

        # Act
        event_loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(event_loop)
            event_loop.run_until_complete(widget._controller.handle_pair_changed("Crypto.ETH/USDC"))
        finally:
            asyncio.set_event_loop(None)
            event_loop.close()

        # Assert
        assert widget._leverage_spin.maximum() == _ETH_PAIR_MAX_LEVERAGE
        ui_controller.set_leverage.assert_awaited_once_with("ETH", 5)

    def test_leverage_quick_selection_includes_100x_button(self) -> None:
        """Expose a 100x leverage shortcut in the trade widget."""
        ui_controller: Any = _UIControllerStub()
        widget = PerpsTradeWidget(ui_controller)

        assert widget._leverage_group.button(100) is not None

    def test_leverage_buttons_append_live_exchange_maximum(self) -> None:
        """Expose the exchange max leverage button even when presets do not include it."""
        ui_controller: Any = _UIControllerStub()
        ui_controller.current_exchange.max_leverage = 125
        widget = PerpsTradeWidget(ui_controller)

        assert widget._leverage_group.button(125) is not None
