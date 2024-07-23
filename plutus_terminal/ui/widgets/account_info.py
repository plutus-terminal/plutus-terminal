"""Widget to display account info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from decimal import Decimal


class AccountInfo(QtWidgets.QWidget):
    """Widget to display account info."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self.main_layout = QtWidgets.QGridLayout(self)
        self.top_bar = TopBar("Account Info")

        self._frame = QtWidgets.QFrame()
        self._frame_layout = QtWidgets.QGridLayout()
        self._balance_label = QtWidgets.QLabel("Available Balance:")
        self._balance_value = QtWidgets.QLabel("$0.00 USD")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._frame.setObjectName("newsFrameQuote")
        self._balance_label.setObjectName("subTitle")
        self._balance_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._balance_value.setObjectName("subTitle")
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar.icon.setPixmap(
            QPixmap(":/icons/account_icon"),
        )

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addWidget(self.top_bar, 0, 0, 1, 2)

        self._frame_layout.addWidget(self._balance_label, 0, 0)
        self._frame_layout.addWidget(self._balance_value, 0, 1)
        self._frame.setLayout(self._frame_layout)
        self.main_layout.addWidget(self._frame, 1, 0, 1, 2)

    def update_balance(self, balance: Decimal) -> None:
        """Update balance."""
        self._balance_value.setText(f"${balance:.3f} USD")
