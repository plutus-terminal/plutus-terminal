"""Widget to display account info."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qasync import asyncSlot

from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


def _humanize_label(label: str) -> str:
    normalized = label.replace("_", " ")
    humanized: list[str] = []
    for character in normalized:
        if humanized and character.isupper() and humanized[-1] not in {" ", "/"}:
            humanized.append(" ")
        humanized.append(character)
    return " ".join("".join(humanized).split()).title()


def _format_decimal_value(value: Decimal, label: str) -> str:
    label_key = label.lower()
    if "fee rate" in label_key or "fee_rate" in label_key:
        return f"{value * Decimal(100):.4f}%"
    if "leverage" in label_key:
        return f"{_plain_decimal_text(value)}x"
    if any(keyword in label_key for keyword in ("balance", "equity", "margin", "pnl", "fee")):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return _plain_decimal_text(value)


def _plain_decimal_text(value: Decimal) -> str:
    value_text = f"{value:f}"
    if "." in value_text:
        return value_text.rstrip("0").rstrip(".")
    return value_text


def _decimal_label_value(label: str, value_text: str) -> str | None:
    normalized_label = label.lower()
    if not any(keyword in normalized_label for keyword in ("fee_rate", "fee rate", "leverage")):
        return None
    try:
        return _format_decimal_value(Decimal(value_text), label)
    except ArithmeticError:
        return None


def _format_account_value(label: str, value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Decimal):
        return _format_decimal_value(value, label)
    if value in (None, ""):
        return "-"

    value_text = str(value)
    decimal_value = _decimal_label_value(label, value_text)
    return value_text if decimal_value is None else decimal_value


class AccountInfo(QtWidgets.QWidget):
    """Widget to display account info."""

    def __init__(
        self,
        ui_controller: UIController,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._ui_controller = ui_controller

        self.main_layout = QtWidgets.QGridLayout(self)
        self.top_bar = TopBar("Account Info")

        self._frame = QtWidgets.QFrame()
        self._frame_layout = QtWidgets.QGridLayout()
        self._balance_label = QtWidgets.QLabel("Available + Unsettled PnL:")
        self._balance_value = QtWidgets.QLabel("$0.00 USD")
        self._exchange_account_info_layout = QtWidgets.QGridLayout()
        self._exchange_account_info_layout.setColumnStretch(0, 1)
        self._exchange_account_info_layout.setColumnStretch(1, 1)
        self.approve_btn = QtWidgets.QPushButton("Approve For Trading")

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.top_bar.icon.setPixmap(
            QPixmap(":/icons/account_info"),
        )
        self._frame.setObjectName("newsFrameQuote")
        self._balance_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._balance_value.setObjectName("subTitle")
        self._balance_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.approve_btn.setProperty("class", "LONG")
        self.approve_btn.setMinimumHeight(30)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.refresh_exchange_account_info()

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.approve_btn.clicked.connect(self._on_approve_for_trading)

        self._ui_controller.message_bus.balance_fetched.connect(self.update_balance)
        self._ui_controller.message_bus.positions_fetched.connect(self._refresh_account_snapshot)

        self._ui_controller.exchange_changed.connect(self._on_new_exchange)

    def refresh_exchange_account_info(self) -> None:
        """Refresh exchange account info."""
        while self._exchange_account_info_layout.count():
            old_widget = self._exchange_account_info_layout.takeAt(
                self._exchange_account_info_layout.count() - 1,
            ).widget()
            old_widget.deleteLater()

        for label, value in self._ui_controller.current_exchange.account_info.items():
            label_widget = QtWidgets.QLabel(_humanize_label(label))
            label_widget.setWordWrap(True)
            value_widget = QtWidgets.QLabel(_format_account_value(label, value))
            value_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_widget.setObjectName("subTitle")
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row_count = self._exchange_account_info_layout.rowCount()
            self._exchange_account_info_layout.addWidget(
                label_widget,
                row_count,
                0,
            )
            self._exchange_account_info_layout.addWidget(
                value_widget,
                row_count,
                1,
            )

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addWidget(self.top_bar, 0, 0, 1, 2)

        self._frame_layout.addWidget(self._balance_label, 0, 0)
        self._frame_layout.addWidget(self._balance_value, 0, 1)
        self._frame_layout.addLayout(self._exchange_account_info_layout, 1, 0, 1, 2)
        self._frame.setLayout(self._frame_layout)
        self.main_layout.addWidget(self._frame, 1, 0, 1, 2)
        self.main_layout.addWidget(self.approve_btn, 2, 0, 1, 2)

        self.setLayout(self.main_layout)

    def update_balance(self, _balance: Decimal) -> None:
        """Update account balance summary and detail rows."""
        self._refresh_account_snapshot()

    def _refresh_account_snapshot(self, *_args: object) -> None:
        """Refresh account info rows and top summary from current exchange state."""
        self.refresh_exchange_account_info()
        balance_value = self._ui_controller.current_exchange.account_info.get(
            "Available Balance + Unsettled PnL",
            Decimal(0),
        )
        if not isinstance(balance_value, Decimal):
            balance_value = Decimal(0)
        self._balance_value.setText(f"${balance_value:,.3f} USD")

    @asyncSlot()
    async def set_approve_btn_visibility(self) -> None:
        """Set approve button visibility."""
        if await self._ui_controller.current_exchange.is_ready_to_trade():
            self.approve_btn.setVisible(False)
        else:
            self.approve_btn.setVisible(True)

    @asyncSlot()
    async def _on_approve_for_trading(self) -> None:
        """Approve for trading."""
        await self._ui_controller.current_exchange.approve_for_trading()
        await self.set_approve_btn_visibility()

    @asyncSlot()
    async def _on_new_exchange(self) -> None:
        """Update widget on new exchange.

        * Refresh exchange account info
        * Set approve button visibility
        """
        self._refresh_account_snapshot()
        await self.set_approve_btn_visibility()
