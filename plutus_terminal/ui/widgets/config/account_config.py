"""Account config widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from plutus_terminal.core.config import CONFIG
from plutus_terminal.ui.widgets.new_account import NewAccountDialog
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import KeyringAccount
    from plutus_terminal.core.password_guard import PasswordGuard


class AccountConfig(QtWidgets.QWidget):
    """Widget to control account configs."""

    def __init__(
        self,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._pass_guard = pass_guard

        self._main_layout = QtWidgets.QVBoxLayout()

        self._account_bar = TopBar("Manage Accounts")
        self._account_scroll_area = QtWidgets.QScrollArea()
        self._account_scroll_widget = QtWidgets.QWidget()
        self._account_box_layout = QtWidgets.QVBoxLayout()
        self._add_account_btn = QtWidgets.QPushButton("Add new Account")

        self._setup_widgets()
        self._setup_layout()
        self.populate_accounts()

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self._account_scroll_area.setWidgetResizable(True)

        self._add_account_btn.setIcon(QtGui.QPixmap(":/icons/user_add"))
        self._add_account_btn.setProperty("class", "LONG")
        self._add_account_btn.setMinimumSize(80, 30)
        self._add_account_btn.clicked.connect(self._add_account)

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._account_bar)

        self._account_scroll_area.setWidget(self._account_scroll_widget)
        self._account_scroll_widget.setLayout(self._account_box_layout)
        self._main_layout.addWidget(self._account_scroll_area)
        account_btn_layout = QtWidgets.QHBoxLayout()
        account_btn_layout.addStretch()
        account_btn_layout.addWidget(self._add_account_btn)
        self._main_layout.addLayout(account_btn_layout)
        self._main_layout.addStretch()

        self.setLayout(self._main_layout)

    def populate_accounts(self) -> None:
        """Populate accounts."""
        # delete all account widgets from account_box_layout
        account_widgets = [
            self._account_box_layout.itemAt(index).widget()
            for index in range(self._account_box_layout.count())
            if isinstance(
                self._account_box_layout.itemAt(index).widget(),
                AccountWidget,
            )
        ]
        for widget in account_widgets:
            self._account_box_layout.removeWidget(widget)
            widget.deleteLater()

        all_accounts = CONFIG.get_all_keyring_accounts()
        for account in all_accounts:
            account_widget = AccountWidget(keyring_account=account)
            self._account_box_layout.addWidget(account_widget)
            account_widget.deleted.connect(self.populate_accounts)

    def _add_account(self) -> None:
        """Add account."""
        new_account_dialog = NewAccountDialog(self._pass_guard)
        new_account_dialog.exec()
        self.populate_accounts()
        Toast.show_message("New account added", type_=ToastType.SUCCESS)


class AccountWidget(QtWidgets.QFrame):
    """Widget to control keyring account."""

    deleted = QtCore.Signal()

    def __init__(
        self,
        keyring_account: KeyringAccount,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._keyring_account = keyring_account

        self._main_layout = QtWidgets.QHBoxLayout()
        self._account_icon = QtWidgets.QLabel()
        self._name_label = QtWidgets.QLabel(str(self._keyring_account.username))
        self._delete_btn = QtWidgets.QPushButton()

        self._setup_widgets()
        self._setup_layout()
        self.resize(self.sizeHint())

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self.setObjectName("config_item")
        self._account_icon.setPixmap(
            QtGui.QPixmap(f":/exchanges/{self._keyring_account.exchange_name}"),
        )
        self._account_icon.setScaledContents(True)
        self._account_icon.setMaximumSize(24, 24)

        self._delete_btn.setIcon(QtGui.QPixmap(":/icons/delete_icon"))
        self._delete_btn.setIconSize(QtCore.QSize(24, 24))
        self._delete_btn.setProperty("class", "borderless")
        self._delete_btn.clicked.connect(self._delete_account)

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._account_icon)
        self._main_layout.addWidget(self._name_label)
        self._main_layout.addStretch()
        self._main_layout.addWidget(self._delete_btn)
        self.setLayout(self._main_layout)

    def _delete_account(self) -> None:
        """Delete account."""
        CONFIG.delete_account(self._keyring_account.id)  # type: ignore
        self.deleted.emit()
        Toast.show_message(
            f"Account '{self._keyring_account.username}' deleted",
            type_=ToastType.SUCCESS,
        )
