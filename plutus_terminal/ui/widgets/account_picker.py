"""Combo box to select account."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QWidget

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.db.models import KeyringAccount
from plutus_terminal.ui.widgets.new_account import NewAccountDialog

if TYPE_CHECKING:
    from plutus_terminal.core.password_guard import PasswordGuard


class AccountPicker(QComboBox):
    """Combo box to select account."""

    account_changed = Signal(KeyringAccount)

    def __init__(self, pass_guard: PasswordGuard, parent: Optional[QWidget] = None) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._pass_guard = pass_guard
        self._current_index = 0

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._add_all_accounts()
        self._set_current_account()
        self.setMinimumWidth(self.sizeHint().width() + 5)
        self.currentIndexChanged.connect(self._on_account_changed)

    def _add_all_accounts(self) -> None:
        """Add all accounts."""
        self.clear()
        all_accounts = CONFIG.get_all_keyring_accounts()
        # Add all accounts
        for account in all_accounts:
            icon = QPixmap(f":/exchanges/{account.exchange_name}")
            self.addItem(
                icon,
                str(account.username).replace("_", " ").capitalize(),
                userData=account,
            )

        # Add custom item to add new accounts
        self.addItem(
            QPixmap(":icons/user_add"),
            "Add new account",
            userData="New Account",
        )

    def _set_current_account(self) -> None:
        """Set current account."""
        for index in range(self.count()):
            if self.itemData(index) == CONFIG.current_keyring_account:
                self.setCurrentIndex(index)
                self._current_index = index
                break

    def _on_account_changed(self, index: int) -> None:
        """Account changed."""
        account = self.itemData(index)

        if account == "New Account":
            new_account_dialog = NewAccountDialog(self._pass_guard)

            if not new_account_dialog.exec():
                self.blockSignals(True)
                self.setCurrentIndex(self._current_index)
                self.blockSignals(False)
                return

            account = new_account_dialog.new_account
            if not account:
                return

            self.blockSignals(True)
            self._add_all_accounts()
            self._set_current_account()
            self.blockSignals(False)
            self.account_changed.emit(account)
            return

        CONFIG.current_keyring_account = account
        self.account_changed.emit(account)
