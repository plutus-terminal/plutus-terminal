"""Widget to display account info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qasync import asyncSlot

from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from decimal import Decimal

    from plutus_terminal.core.exchange.base import ExchangeBase


class AccountInfo(QtWidgets.QWidget):
    """Widget to display account info."""

    def __init__(
        self,
        exchange_account_info: dict[str, Any],
        is_ready_to_trade: Callable[[], Coroutine[Any, Any, bool]],
        approve_for_trading: Callable[[], Coroutine[Any, Any, None]],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._exchange_account_info = exchange_account_info
        self._is_ready_to_trade = is_ready_to_trade
        self._approve_for_trading = approve_for_trading

        self.main_layout = QtWidgets.QGridLayout(self)
        self.top_bar = TopBar("Account Info")

        self._frame = QtWidgets.QFrame()
        self._frame_layout = QtWidgets.QGridLayout()
        self._balance_label = QtWidgets.QLabel("Available Balance:")
        self._balance_value = QtWidgets.QLabel("$0.00 USD")
        self._exchange_account_info_layout = QtWidgets.QGridLayout()
        self.approve_btn = QtWidgets.QPushButton("Approve For Trading")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.top_bar.icon.setPixmap(
            QPixmap(":/icons/account_info"),
        )
        self._frame.setObjectName("newsFrameQuote")
        self._balance_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._balance_value.setObjectName("subTitle")
        self.approve_btn.setProperty("class", "LONG")
        self.approve_btn.setMinimumHeight(30)
        self.approve_btn.clicked.connect(self._on_approve_for_trading)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.refresh_exchange_account_info(self._exchange_account_info)

    def refresh_exchange_account_info(self, exchange_account_info: dict[str, Any]) -> None:
        """Refresh exchange account info."""
        self._exchange_account_info = exchange_account_info

        # clear exchange_account_info layout
        while self._exchange_account_info_layout.count():
            old_widget = self._exchange_account_info_layout.takeAt(
                self._exchange_account_info_layout.count() - 1,
            ).widget()
            old_widget.deleteLater()

        for label, value in self._exchange_account_info.items():
            label_widget = QtWidgets.QLabel(label)
            value_widget = QtWidgets.QLabel(str(value))
            value_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            value_widget.setObjectName("subTitle")
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

    def update_balance(self, balance: Decimal) -> None:
        """Update balance."""
        self._balance_value.setText(f"${balance:.3f} USD")

    @asyncSlot()
    async def set_approve_btn_visibility(self) -> None:
        """Set approve button visibility."""
        if await self._is_ready_to_trade():
            self.approve_btn.setVisible(False)
        else:
            self.approve_btn.setVisible(True)

    @asyncSlot()
    async def _on_approve_for_trading(self) -> None:
        """Approve for trading."""
        await self._approve_for_trading()
        await self.set_approve_btn_visibility()

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._is_ready_to_trade = new_exchange.is_ready_to_trade
        self._approve_for_trading = new_exchange.approve_for_trading
        self.refresh_exchange_account_info(new_exchange.account_info)
