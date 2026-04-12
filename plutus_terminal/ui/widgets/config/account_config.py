"""Account config widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from plutus_terminal.core.config import AppConfig
from plutus_terminal.ui.widgets.new_account import NewAccountDialog
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import KeyringAccount
    from plutus_terminal.core.password_guard import PasswordGuard


class AccountConfig(QtWidgets.QWidget):
    """Widget to control account configs."""

    _CARD_MIN_WIDTH = 320

    def __init__(
        self,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._pass_guard = pass_guard
        self._app_config = app_config

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._account_bar = TopBar("Manage Accounts")
        self._account_hint = QtWidgets.QLabel(
            "Accounts stay local to this device. Add or remove exchange profiles here.",
        )
        self._account_scroll_area = QtWidgets.QScrollArea()
        self._account_scroll_widget = QtWidgets.QWidget()
        self._account_grid_layout = QtWidgets.QGridLayout()
        self._add_account_btn = QtWidgets.QPushButton("Add New Account")
        self._account_widgets: list[AccountWidget] = []

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()
        self.populate_accounts()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._account_hint.setWordWrap(True)
        self._account_hint.setObjectName("subText")

        self._account_scroll_area.setWidgetResizable(True)
        self._account_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self._account_scroll_widget.setLayout(self._account_grid_layout)

        self._account_grid_layout.setContentsMargins(0, 0, 0, 0)
        self._account_grid_layout.setHorizontalSpacing(12)
        self._account_grid_layout.setVerticalSpacing(12)

        self._add_account_btn.setIcon(QtGui.QPixmap(":/icons/user_add"))
        self._add_account_btn.setProperty("class", "APPROVED")
        self._add_account_btn.setMinimumSize(150, 34)
        self._account_bar.add_widget(self._add_account_btn)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._add_account_btn.clicked.connect(self._add_account)

        self._app_config.account_created.connect(self.populate_accounts)
        self._app_config.account_deleted.connect(self.populate_accounts)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._account_bar)
        self._main_layout.addWidget(self._account_hint)
        self._account_scroll_area.setWidget(self._account_scroll_widget)
        self._main_layout.addWidget(self._account_scroll_area)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Refresh the card grid when the widget is resized."""
        super().resizeEvent(event)
        self._relayout_accounts()

    def populate_accounts(self) -> None:
        """Populate accounts."""
        for widget in self._account_widgets:
            self._account_grid_layout.removeWidget(widget)
            widget.deleteLater()

        self._account_widgets = [
            AccountWidget(keyring_account=account, app_config=self._app_config)
            for account in AppConfig.get_all_accounts()
        ]
        self._relayout_accounts()

    def refresh_from_config(self) -> None:
        """Reload account cards from the current saved config state."""
        self.populate_accounts()

    def _relayout_accounts(self) -> None:
        """Arrange account cards based on the available width."""
        while self._account_grid_layout.count():
            item = self._account_grid_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(self._account_scroll_widget)

        viewport_width = max(self._account_scroll_area.viewport().width(), self.width())
        columns = max(1, viewport_width // self._CARD_MIN_WIDTH)
        for index, widget in enumerate(self._account_widgets):
            row = index // columns
            column = index % columns
            self._account_grid_layout.addWidget(widget, row, column)

        for column in range(columns):
            self._account_grid_layout.setColumnStretch(column, 1)
        self._account_grid_layout.setRowStretch(
            (len(self._account_widgets) + columns - 1) // columns,
            1,
        )

    def _add_account(self) -> None:
        """Add account."""
        new_account_dialog = NewAccountDialog(self._pass_guard, self._app_config)
        new_account_dialog.exec()
        if not new_account_dialog.new_account:
            return
        self.populate_accounts()
        Toast.show_message("New account added", type_=ToastType.SUCCESS)


class AccountWidget(QtWidgets.QFrame):
    """Widget to control keyring account."""

    def __init__(
        self,
        keyring_account: KeyringAccount,
        app_config: AppConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._keyring_account = keyring_account
        self._app_config = app_config

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._top_layout = QtWidgets.QHBoxLayout()
        self._meta_layout = QtWidgets.QVBoxLayout()
        self._account_icon = QtWidgets.QLabel()
        self._name_label = QtWidgets.QLabel(str(self._keyring_account.username))
        self._exchange_label = QtWidgets.QLabel(str(self._keyring_account.exchange_name).title())
        self._delete_btn = QtWidgets.QPushButton()

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setObjectName("config_item")
        self.setMinimumWidth(260)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        self._account_icon.setPixmap(
            QtGui.QPixmap(f":/exchanges/{self._keyring_account.exchange_name}"),
        )
        self._account_icon.setScaledContents(True)
        self._account_icon.setFixedSize(28, 28)

        self._name_label.setObjectName("title")
        self._name_label.setWordWrap(True)
        self._exchange_label.setObjectName("subText")

        self._delete_btn.setIcon(QtGui.QPixmap(":/icons/delete_icon"))
        self._delete_btn.setIconSize(QtCore.QSize(22, 22))
        self._delete_btn.setProperty("class", "borderless")
        self._delete_btn.setToolTip("Delete Account")
        self._delete_btn.clicked.connect(self._delete_account)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._meta_layout.addWidget(self._name_label)
        self._meta_layout.addWidget(self._exchange_label)

        self._top_layout.addWidget(self._account_icon, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        self._top_layout.addLayout(self._meta_layout)
        self._top_layout.addStretch()
        self._top_layout.addWidget(
            self._delete_btn,
            alignment=QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )

        self._main_layout.addLayout(self._top_layout)

    def _delete_account(self) -> None:
        """Delete account."""
        account_id = self._keyring_account.get_id()
        if account_id is None:
            return
        self._app_config.delete_account(int(account_id))
        Toast.show_message(
            f"Account '{self._keyring_account.username}' deleted",
            type_=ToastType.SUCCESS,
        )
