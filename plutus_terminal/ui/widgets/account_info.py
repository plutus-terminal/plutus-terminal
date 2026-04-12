"""Widget to display account info."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from plutus_terminal.controller.widgets.account_info_controller import AccountInfoController
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


_BALANCE_SUMMARY_KEY = "Available Balance + Unsettled PnL"
_BALANCE_SUMMARY_LABEL = "Total Balance"
_BALANCE_SUMMARY_TOOLTIP = (
    "Total Balance includes your available balance plus unsettled PnL from open positions."
)
_BALANCE_DETAIL_KEYS = (
    "Available Balance",
    "Unsettled PnL",
    "Free Balance",
)
_BALANCE_KEYS = {_BALANCE_SUMMARY_KEY, *_BALANCE_DETAIL_KEYS}


def _humanize_label(label: str) -> str:
    normalized = label.replace("_", " ")
    humanized: list[str] = []
    for character in normalized:
        if humanized and character.isupper() and humanized[-1] not in {" ", "/"}:
            humanized.append(" ")
        humanized.append(character)
    formatted_label = " ".join("".join(humanized).split()).title()
    return formatted_label.replace("Pn L", "PnL")


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


def _format_balance_summary(value: object) -> str:
    if isinstance(value, Decimal):
        return f"${value:,.3f} USD"
    return _format_account_value(_BALANCE_SUMMARY_KEY, value)


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        child_item = layout.takeAt(layout.count() - 1)
        child_widget = child_item.widget()
        child_layout = child_item.layout()
        if child_widget is not None:
            child_widget.deleteLater()
            continue
        if child_layout is not None:
            _clear_layout(child_layout)


def _partition_account_info(
    account_info: dict[str, object],
) -> tuple[dict[str, object], list[tuple[str, object]]]:
    balance_info = {
        label: account_info[label]
        for label in (_BALANCE_SUMMARY_KEY, *_BALANCE_DETAIL_KEYS)
        if label in account_info
    }
    detail_rows = [
        (label, value) for label, value in account_info.items() if label not in _BALANCE_KEYS
    ]
    return balance_info, detail_rows


class AccountInfo(QtWidgets.QWidget):
    """Widget to display account info."""

    def __init__(
        self,
        ui_controller: UIController,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._ui_controller = ui_controller

        self.main_layout = QtWidgets.QGridLayout(self)
        self.top_bar = TopBar("Account Info")

        self._frame = QtWidgets.QFrame()
        self._frame_layout = QtWidgets.QVBoxLayout()
        self._balance_overview_frame = QtWidgets.QFrame()
        self._balance_overview_layout = QtWidgets.QVBoxLayout()
        self._balance_label = QtWidgets.QLabel(_BALANCE_SUMMARY_LABEL)
        self._balance_value = QtWidgets.QLabel("$0.00 USD")
        self._toggle_details_button = QtWidgets.QPushButton()
        self._details_container = QtWidgets.QWidget()
        self._details_container_layout = QtWidgets.QVBoxLayout()
        self._balance_breakdown_frame = QtWidgets.QFrame()
        self._balance_breakdown_layout = QtWidgets.QGridLayout()
        self._details_frame = QtWidgets.QFrame()
        self._exchange_account_info_layout = QtWidgets.QGridLayout()
        self._exchange_account_info_layout.setColumnStretch(0, 1)
        self._exchange_account_info_layout.setColumnStretch(1, 1)
        self.approve_btn = QtWidgets.QPushButton("Approve For Trading")

        self._setup_widgets()
        self._setup_layout()
        self._controller = AccountInfoController(ui_controller, self)

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.top_bar.icon.setPixmap(
            QPixmap(":/icons/account_info"),
        )
        self._balance_overview_frame.setObjectName("newsFrameQuote")
        self._balance_breakdown_frame.setObjectName("newsFrameQuote")
        self._details_frame.setObjectName("newsFrameQuote")
        self._balance_label.setWordWrap(True)
        self._balance_label.setToolTip(_BALANCE_SUMMARY_TOOLTIP)
        self._balance_value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._balance_value.setObjectName("subTitle")
        self._balance_value.setToolTip(_BALANCE_SUMMARY_TOOLTIP)
        self._balance_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._toggle_details_button.clicked.connect(self._toggle_details)
        self._toggle_details_button.setObjectName("actionButton")
        self._toggle_details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_details_button.setText(self._details_toggle_text(False))
        self._balance_breakdown_layout.setColumnStretch(0, 1)
        self._balance_breakdown_layout.setColumnStretch(1, 1)
        self._details_container_layout.setContentsMargins(0, 0, 0, 0)
        self._details_container_layout.setSpacing(8)
        self._details_container.setLayout(self._details_container_layout)
        self._details_container.hide()
        self.approve_btn.setProperty("class", "LONG")
        self.approve_btn.setMinimumHeight(30)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setContentsMargins(0, 0, 0, 0)

        self.refresh_exchange_account_info()

    def refresh_exchange_account_info(self) -> None:
        """Refresh exchange account info."""
        balance_info, detail_rows = _partition_account_info(
            self._ui_controller.current_exchange.account_info,
        )
        self._refresh_balance_overview(balance_info)
        _clear_layout(self._exchange_account_info_layout)

        for label, value in detail_rows:
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

    def _refresh_balance_overview(self, balance_info: dict[str, object]) -> None:
        """Refresh grouped balance summary and supporting balance details."""
        summary_value = balance_info.get(_BALANCE_SUMMARY_KEY, Decimal(0))
        self._balance_value.setText(_format_balance_summary(summary_value))

        _clear_layout(self._balance_breakdown_layout)
        row_count = 0
        for label in _BALANCE_DETAIL_KEYS:
            if label not in balance_info:
                continue
            label_widget = QtWidgets.QLabel(_humanize_label(label))
            label_widget.setWordWrap(True)
            value_widget = QtWidgets.QLabel(_format_account_value(label, balance_info[label]))
            value_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_widget.setObjectName("subTitle")
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._balance_breakdown_layout.addWidget(label_widget, row_count, 0)
            self._balance_breakdown_layout.addWidget(value_widget, row_count, 1)
            row_count += 1

        self._balance_breakdown_frame.setVisible(row_count > 0)
        self._details_frame.setVisible(self._exchange_account_info_layout.count() > 0)

    @staticmethod
    def _details_toggle_text(is_expanded: bool) -> str:
        """Return CTA text for the expandable details section."""
        return "Hide Balance Details" if is_expanded else "Show Balance Details"

    def _toggle_details(self) -> None:
        """Toggle the visibility of the expandable account details section."""
        is_expanded = self._details_container.isHidden()
        self._details_container.setVisible(is_expanded)
        self._toggle_details_button.setText(self._details_toggle_text(is_expanded))

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addWidget(self.top_bar, 0, 0, 1, 2)

        self._balance_breakdown_frame.setLayout(self._balance_breakdown_layout)
        self._balance_overview_layout.addWidget(self._balance_label)
        self._balance_overview_layout.addWidget(self._balance_value)
        self._balance_overview_frame.setLayout(self._balance_overview_layout)
        self._details_frame.setLayout(self._exchange_account_info_layout)
        self._details_container_layout.addWidget(self._balance_breakdown_frame)

        self._frame_layout.addWidget(self._balance_overview_frame)
        self._frame_layout.addWidget(self._toggle_details_button)
        self._frame_layout.addWidget(self._details_container)
        self._frame_layout.addWidget(self._details_frame)
        self._frame.setLayout(self._frame_layout)
        self.main_layout.addWidget(self._frame, 1, 0, 1, 2)
        self.main_layout.addWidget(self.approve_btn, 2, 0, 1, 2)

        self.setLayout(self.main_layout)

    def update_balance(self, _balance: Decimal) -> None:
        """Update account balance summary and detail rows."""
        self._controller.refresh_for_balance(_balance)

    def _refresh_account_snapshot(self, *_args: object) -> None:
        """Refresh account info rows and top summary from current exchange state."""
        self._controller.refresh_account_snapshot(*_args)

    async def set_approve_btn_visibility(self) -> None:
        """Set approve button visibility."""
        await self._controller.set_approve_btn_visibility()

    async def _on_approve_for_trading(self) -> None:
        """Approve for trading."""
        await self._controller.handle_approve_for_trading()

    async def _on_new_exchange(self) -> None:
        """Update widget on new exchange.

        * Refresh exchange account info
        * Set approve button visibility
        """
        await self._controller.handle_exchange_changed()
