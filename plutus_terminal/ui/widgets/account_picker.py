"""Combo box to select account."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QWidget
from qasync import asyncSlot

from plutus_terminal.ui.widgets.new_account import NewAccountDialog

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


class AccountPicker(QComboBox):
    """Combo box to select account."""

    def __init__(self, ui_controller: UIController, parent: Optional[QWidget] = None) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._ui_controller = ui_controller
        self._app_config = ui_controller.app_config
        self._pass_guard = ui_controller.pass_guard
        self._current_index = 0

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._add_all_accounts()
        self.setMinimumWidth(self.sizeHint().width() + 5)
        self.currentIndexChanged.connect(self._on_account_changed)

        self._app_config.account_created.connect(self._add_all_accounts)
        self._app_config.account_deleted.connect(self._add_all_accounts)

    def _add_all_accounts(self) -> None:
        """Add all accounts."""
        self.blockSignals(True)

        self.clear()
        all_accounts = self._app_config.get_all_accounts()
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

        self._set_current_account()
        self.blockSignals(False)

    def _set_current_account(self) -> None:
        """Set current account."""
        for index in range(self.count()):
            if self.itemData(index) == self._app_config.current_keyring_account:
                self.setCurrentIndex(index)
                self._current_index = index
                break

    @asyncSlot()
    async def _on_account_changed(self, index: int) -> None:
        """Account changed."""
        account = self.itemData(index)

        if account == "New Account":
            new_account_dialog = NewAccountDialog(self._pass_guard, self._app_config)

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
            return

        self._app_config.current_keyring_account = account
