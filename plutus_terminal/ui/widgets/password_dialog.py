"""Password dialog widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QPixmap

from plutus_terminal.core.exceptions import InvalidPasswordError

if TYPE_CHECKING:
    from plutus_terminal.core.password_guard import PasswordGuard


class BasePasswordDialog(QtWidgets.QDialog):
    """Base password dialog."""

    def __init__(
        self,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)

        self._pass_guard = pass_guard

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self._info_layout = QtWidgets.QGridLayout()
        self._lock_icon = QtWidgets.QLabel()

        self._info_label = QtWidgets.QLabel()

        self._password_label = QtWidgets.QLabel("Password")
        self._password_line_edit = QtWidgets.QLineEdit()

        self._status_bar = QtWidgets.QStatusBar()
        self._status_label = QtWidgets.QLabel()

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setMinimumSize(300, 300)
        self._info_layout.setSpacing(10)

        self._lock_icon.setPixmap(QPixmap(":/icons/lock_icon"))
        self._lock_icon.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self._lock_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        self._info_label.setObjectName("title")
        self._info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        self._password_line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._status_bar.setSizeGripEnabled(False)
        self._status_label.setProperty("class", "error")
        self._status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._status_bar.addWidget(self._status_label, 1)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addLayout(self._info_layout)

        self._info_layout.addWidget(self._lock_icon, 0, 0, 1, 2)
        self._info_layout.addWidget(self._info_label, 1, 0, 1, 2)

        self._info_layout.addWidget(self._password_label, 2, 0)
        self._info_layout.addWidget(self._password_line_edit, 2, 1)

        self.main_layout.addWidget(self._status_bar)

    def show_status_message(self, message: str) -> None:
        """Show status message."""
        self._status_label.setText(message)


class CreatePasswordDialog(BasePasswordDialog):
    """Dialog for creating new password."""

    def __init__(
        self,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        self._confirm_label = QtWidgets.QLabel("Confirm Password")
        self._confirm_line_edit = QtWidgets.QLineEdit()

        self._create_btn = QtWidgets.QPushButton("Create Password")
        super().__init__(pass_guard=pass_guard, parent=parent)

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        super()._setup_widgets()
        self.setWindowTitle("Create New Password")
        self._info_label.setText("Enter a new password")
        self._confirm_line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        self._create_btn.setProperty("class", "LONG")
        self._create_btn.setMinimumHeight(40)
        self._create_btn.clicked.connect(self._create_password)

    def _setup_layout(self) -> None:
        """Configure layout."""
        super()._setup_layout()
        self._info_layout.addWidget(self._confirm_label, 3, 0)
        self._info_layout.addWidget(self._confirm_line_edit, 3, 1)

        self._info_layout.addWidget(self._create_btn, 4, 0, 1, 2)

    def _create_password(self) -> None:
        """Validate password and accept."""
        if not self._password_line_edit.text() or not self._confirm_line_edit.text():
            self.show_status_message(
                "Password cannot be empty",
            )
            return

        if self._password_line_edit.text() != self._confirm_line_edit.text():
            self.show_status_message(
                "Passwords do not match",
            )
            return

        self._pass_guard.password = self._password_line_edit.text()
        self.accept()


class UnlockPasswordDialog(BasePasswordDialog):
    """Dialog for unlocking password."""

    def __init__(
        self,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        self._unlock_btn = QtWidgets.QPushButton("Unlock Password")
        super().__init__(pass_guard=pass_guard, parent=parent)

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        super()._setup_widgets()
        self.setWindowTitle("Unlock Terminal")

        self._info_label.setText("Enter your password")
        self._unlock_btn.setProperty("class", "LONG")
        self._unlock_btn.setMinimumHeight(40)
        self._unlock_btn.clicked.connect(self._unlock_password)

    def _setup_layout(self) -> None:
        """Configure layout."""
        super()._setup_layout()
        self._info_layout.addWidget(self._unlock_btn, 3, 0, 1, 2)

    def _unlock_password(self) -> None:
        """Validate password and accept."""
        try:
            self._pass_guard.password = self._password_line_edit.text()
        except InvalidPasswordError:
            self.show_status_message(
                "Invalid password",
            )
            return
        self.accept()
