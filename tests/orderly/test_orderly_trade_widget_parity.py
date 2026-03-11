# ruff: noqa: S101, SLF001

"""Focused parity tests for the Orderly trade widget."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar
import unittest

from PySide6 import QtCore, QtWidgets

from plutus_terminal.core.types_ import PerpsTradeType
from plutus_terminal.ui.widgets.perps_trade import PerpsTradeWidget


class _MessageBus(QtCore.QObject):
    """Minimal signal-only message bus for widget tests."""

    subscribed_prices_fetched = QtCore.Signal(object)
    balance_fetched = QtCore.Signal(object)


class _AppConfig(QtCore.QObject):
    """Minimal app config exposing the widget signal contract."""

    trade_value_high_changed = QtCore.Signal()
    trade_value_low_changed = QtCore.Signal()
    trade_value_lowest_changed = QtCore.Signal()
    leverage_changed = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.trade_value_lowest = Decimal("10")
        self.trade_value_low = Decimal("25")
        self.trade_value_medium = Decimal("50")
        self.trade_value_high = Decimal("100")
        self.leverage = 5


class _ExchangeStub:
    """Minimal exchange surface consumed by PerpsTradeWidget."""

    quote_symbol: ClassVar[str] = "USDC"
    max_leverage: ClassVar[int] = 50
    available_pairs: ClassVar[set[str]] = {"Crypto.BTC/USDC"}
    default_pair: ClassVar[str] = "Crypto.BTC/USDC"
    pair_prefix: ClassVar[str] = "Crypto."
    pair_suffix: ClassVar[str] = ""
    pair_separator: ClassVar[str] = "/"
    cached_prices: ClassVar[dict[str, dict[str, Decimal]]] = {
        "Crypto.BTC/USDC": {"price": Decimal("97500")}
    }
    stable_balance: ClassVar[Decimal] = Decimal("100")

    @staticmethod
    def format_simple_pair_from_pair(pair: str) -> str:
        return pair.replace("Crypto.", "")

    @staticmethod
    def format_coin_from_pair(_pair: str) -> str:
        return "BTC"

    @staticmethod
    def calculate_margin_fee(_position_size: Decimal) -> Decimal:
        return Decimal("1")

    @staticmethod
    def calculate_liquidation_price(_position: object) -> Decimal:
        return Decimal("90000")


class _UIControllerStub(QtCore.QObject):
    """Minimal controller surface consumed by PerpsTradeWidget."""

    exchange_changed = QtCore.Signal()
    pair_changed = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_exchange = _ExchangeStub()
        self.app_config = _AppConfig()
        self.message_bus = _MessageBus()

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
