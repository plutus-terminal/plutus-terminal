"""Widget to display account info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from plutus_terminal.ui.presenter.account_info_presenter import AccountInfoView
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.ui.presenter.account_info_presenter import AccountInfoPresenter


class AccountInfo(QtWidgets.QWidget, AccountInfoView):
    """Widget to display account info."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._presenter: Optional[AccountInfoPresenter] = None

        self.main_layout = QtWidgets.QGridLayout(self)
        self.top_bar = TopBar("Account Info")

        self._frame = QtWidgets.QFrame()
        self._frame_layout = QtWidgets.QGridLayout()
        self._balance_label = QtWidgets.QLabel("Available Balance:")
        self._balance_value = QtWidgets.QLabel("$0.00 USD")
        self._exchange_account_info_layout = QtWidgets.QGridLayout()
        self.approve_btn = QtWidgets.QPushButton("Approve For Trading")

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()

    def set_presenter(self, presenter: AccountInfoPresenter) -> None:
        """Set the presenter."""
        self._presenter = presenter
        self._presenter.start()

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
        self.main_layout.setContentsMargins(0, 0, 0, 0)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.approve_btn.clicked.connect(self._on_approve_clicked)

    def _on_approve_clicked(self) -> None:
        """Handle approve click."""
        if self._presenter:
            self._presenter.on_approve_clicked()

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

    def set_balance(self, balance: str) -> None:
        """Set balance text."""
        self._balance_value.setText(balance)

    def set_exchange_info(self, info: dict[str, str]) -> None:
        """Set exchange info."""
        while self._exchange_account_info_layout.count():
            old_widget = self._exchange_account_info_layout.takeAt(
                self._exchange_account_info_layout.count() - 1,
            ).widget()
            old_widget.deleteLater()

        for label, value in info.items():
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

    def set_approve_button_visible(self, visible: bool) -> None:
        """Set approve button visibility."""
        self.approve_btn.setVisible(visible)

    def closeEvent(self, event) -> None:
        """Stop presenter on close."""
        if self._presenter:
            self._presenter.stop()
        super().closeEvent(event)
