# ruff: noqa: S101, SLF001

"""Focused parity tests for the Orderly account info widget."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
import unittest

from PySide6 import QtCore, QtWidgets

from plutus_terminal.ui.widgets.account_info import AccountInfo


class _MessageBus(QtCore.QObject):
    """Minimal signal-only message bus for account widget tests."""

    balance_fetched = QtCore.Signal(object)
    positions_fetched = QtCore.Signal(object)


class _ExchangeStub:
    """Mutable exchange stub exposing account info rows."""

    def __init__(self) -> None:
        self.account_info = {
            "Available Balance + Unsettled PnL": Decimal("100"),
            "Free Balance": Decimal("80"),
            "Available Balance": Decimal("95"),
            "Unsettled PnL": Decimal("5"),
        }

    async def is_ready_to_trade(self) -> bool:
        """Keep the approve button hidden in tests."""
        return True

    async def approve_for_trading(self) -> None:
        """Satisfy widget callback contract."""


class _UIControllerStub(QtCore.QObject):
    """Minimal controller surface consumed by AccountInfo."""

    exchange_changed = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.current_exchange = _ExchangeStub()
        self.message_bus = _MessageBus()


def _layout_value_for_label(widget: AccountInfo, label_text: str) -> str:
    """Resolve the rendered value text for one account-info row label."""
    layout = widget._exchange_account_info_layout
    expected_label = " ".join(label_text.lower().split())
    for row in range(layout.rowCount()):
        label_item = layout.itemAtPosition(row, 0)
        value_item = layout.itemAtPosition(row, 1)
        if label_item is None or value_item is None:
            continue
        label_widget = label_item.widget()
        value_widget = value_item.widget()
        if not isinstance(label_widget, QtWidgets.QLabel) or not isinstance(
            value_widget, QtWidgets.QLabel
        ):
            continue
        actual_label = " ".join(label_widget.text().lower().split())
        if actual_label == expected_label:
            return value_widget.text()
    raise AssertionError(label_text)


class OrderlyAccountInfoWidgetParityTests(unittest.TestCase):
    """Verify account-info balance rows stay aligned with live trading state."""

    @classmethod
    def setUpClass(cls) -> None:
        """Ensure one QApplication exists for widget tests."""
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_balance_signal_refreshes_summary_and_rows_from_exchange_state(self) -> None:
        """Refresh both the top summary and detail rows when balances/positions change."""
        # Arrange
        ui_controller: Any = _UIControllerStub()
        widget = AccountInfo(ui_controller)
        ui_controller.current_exchange.account_info = {
            "Available Balance + Unsettled PnL": Decimal("112.5"),
            "Free Balance": Decimal("87.5"),
            "Available Balance": Decimal("100"),
            "Unsettled PnL": Decimal("12.5"),
        }

        # Act
        ui_controller.message_bus.balance_fetched.emit(Decimal("0"))

        # Assert
        assert widget._balance_value.text() == "$112.500 USD"
        assert _layout_value_for_label(widget, "Free Balance") == "87.5"
        assert _layout_value_for_label(widget, "Available Balance") == "100"
        assert _layout_value_for_label(widget, "Available Balance + Unsettled Pn L") == "112.5"
