"""New account dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import keyring
import orjson
from PySide6 import QtWidgets
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QPixmap, QRegularExpressionValidator

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exchange.valid_exchanges import VALID_EXCHANGES
from plutus_terminal.core.types_ import ExchangeType
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import KeyringAccount
    from plutus_terminal.core.password_guard import PasswordGuard


class NewAccountDialog(QtWidgets.QDialog):
    """Dialog for creating new account."""

    def __init__(
        self,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)

        self._pass_guard = pass_guard
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.new_account: Optional[KeyringAccount] = None

        self._add_acc_icon = QtWidgets.QLabel()
        self._info_group = QtWidgets.QGroupBox("Account Info:")
        self._info_layout = QtWidgets.QGridLayout()
        self._type_label = QtWidgets.QLabel("Exchange Type")
        self._type_combo_box = QtWidgets.QComboBox()
        self._exchange_label = QtWidgets.QLabel("Exchange")
        self._exchange_combo_box = QtWidgets.QComboBox()
        self._account_label = QtWidgets.QLabel("Account Name")
        self._account_line_edit = QtWidgets.QLineEdit()

        self._secrets_group = QtWidgets.QGroupBox("Secrets:")
        self._secrets_layout = QtWidgets.QGridLayout()
        self._secrets_labels: list[QtWidgets.QLabel] = []
        self._secrets_line_edits: list[QtWidgets.QLineEdit] = []

        self._log_label = QtWidgets.QLabel()
        self._create_btn = QtWidgets.QPushButton("Create New Account")

        self._setup_widgets()
        self._setup_connections()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setWindowTitle("Create New Account")
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setMinimumSize(500, 500)

        self._add_acc_icon.setPixmap(QPixmap(":/icons/new_acc"))
        self._add_acc_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._add_acc_icon.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

        self._info_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._type_combo_box.addItems(
            [exchange_type.name for exchange_type in ExchangeType],
        )
        self._fill_exchange_options()

        self._secrets_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

        self._account_line_edit.setPlaceholderText("Enter account name...")
        # Only allow letters, numbers, and underscores up to 24 characters
        regex = QRegularExpression("^[A-Za-z0-9_]{1,24}$")
        self._account_line_edit.setValidator(QRegularExpressionValidator(regex, self))

        self._log_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._log_label.setProperty("class", "error")

        self._create_btn.setMinimumSize(150, 40)
        self._create_btn.setProperty("class", "LONG")

    def _setup_connections(self) -> None:
        """Configure connections."""
        self._type_combo_box.currentTextChanged.connect(self._fill_exchange_options)
        self._exchange_combo_box.currentTextChanged.connect(self._fill_secrets_group)
        self._create_btn.clicked.connect(self._create_new_account)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addWidget(self._add_acc_icon)
        self._info_layout.addWidget(self._type_label, 0, 0)
        self._info_layout.addWidget(self._type_combo_box, 0, 1)
        self._info_layout.addWidget(self._exchange_label, 1, 0)
        self._info_layout.addWidget(self._exchange_combo_box, 1, 1)
        self._info_layout.addWidget(self._account_label, 2, 0)
        self._info_layout.addWidget(self._account_line_edit, 2, 1)
        self._info_group.setLayout(self._info_layout)
        self.main_layout.addWidget(self._info_group)

        self._secrets_group.setLayout(self._secrets_layout)
        self.main_layout.addWidget(self._secrets_group)
        self.main_layout.addWidget(self._log_label)
        self.main_layout.addWidget(
            self._create_btn,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

    def _fill_exchange_options(self) -> None:
        """Fill exchange combo box."""
        self._exchange_combo_box.blockSignals(True)

        self._exchange_combo_box.clear()
        selected_type = self._type_combo_box.currentText()

        for exchange_name, exchange in VALID_EXCHANGES.items():
            if exchange.exchange_type() == ExchangeType[selected_type]:
                icon = QPixmap(f":/exchanges/{exchange_name}")
                self._exchange_combo_box.addItem(icon, exchange.name(), userData=exchange_name)

        self._fill_secrets_group()

        self._exchange_combo_box.blockSignals(False)

    def _fill_secrets_group(self) -> None:
        """Fill secrets group."""
        # Clear _secrets_layout widgets
        while self._secrets_layout.count():
            old_widget = self._secrets_layout.takeAt(
                self._secrets_layout.count() - 1,
            ).widget()
            old_widget.deleteLater()

        self._secrets_labels.clear()
        self._secrets_line_edits.clear()

        selected_exchange = self._exchange_combo_box.currentData()
        exchange = VALID_EXCHANGES[selected_exchange]
        new_account_info = exchange.new_account_info()

        for secret in new_account_info["secrets"]:
            label = QtWidgets.QLabel(secret)
            line_edit = QtWidgets.QLineEdit()
            self._secrets_layout.addWidget(label, len(self._secrets_labels), 0)
            self._secrets_layout.addWidget(line_edit, len(self._secrets_labels), 1)
            self._secrets_labels.append(label)
            self._secrets_line_edits.append(line_edit)

    def _create_new_account(self) -> None:
        """Create new account on database."""
        # Validate if all fields are filled
        toast_id = Toast.show_message(
            "Creating account...",
            type_=ToastType.MESSAGE,
        )
        if not self._account_line_edit.text():
            self._log_label.setText("Account name cannot be empty!")
            Toast.update_message(
                toast_id,
                "Account name cannot be empty!",
                ToastType.ERROR,
            )
            return
        for line_edit in self._secrets_line_edits:
            if not line_edit.text():
                self._log_label.setText("Secrets cannot be empty!")
                Toast.update_message(
                    toast_id,
                    "Secrets cannot be empty!",
                    ToastType.ERROR,
                )
                return

        account_name = self._account_line_edit.text()
        secrets = [secret.text() for secret in self._secrets_line_edits]
        exchange_name = self._exchange_combo_box.currentData()

        # Validate secrets
        exchange = VALID_EXCHANGES[exchange_name]
        valid, error = exchange.validate_secrets(secrets)
        if not valid:
            self._log_label.setText(error)
            Toast.update_message(toast_id, error, ToastType.ERROR)
            return

        self.new_account = CONFIG.create_account(
            username=account_name,
            exchange_type=ExchangeType[self._type_combo_box.currentText()],
            exchange_name=exchange_name,
        )
        CONFIG.current_keyring_account = self.new_account

        encrypted_secrets = self._pass_guard.encrypt(
            orjson.dumps(secrets).decode("utf-8"),
        )

        # Save secrets to keyring
        keyring.set_password(
            "plutus-terminal",
            str(account_name),
            encrypted_secrets,
        )

        self._log_label.setText("Account created successfully!")
        Toast.update_message(
            toast_id,
            "Account created successfully!",
            ToastType.SUCCESS,
        )
        super().accept()
