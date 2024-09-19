"""Top bar widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtGui import QPixmap

from plutus_terminal.ui.widgets.account_picker import AccountPicker
from plutus_terminal.ui.widgets.clock import WebClock

if TYPE_CHECKING:
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.ui.widgets.config import ConfigDialog


class UserTopBar(QtWidgets.QWidget):
    """Top bar widget."""

    def __init__(
        self,
        config_dialog: ConfigDialog,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self.setObjectName("user_top_bar")
        self.main_layout = QtWidgets.QVBoxLayout()
        self._bar_layout = QtWidgets.QHBoxLayout()

        self.account_picker = AccountPicker(pass_guard)
        self._clock = WebClock()
        self._config_dialog = config_dialog
        self._config_button = QtWidgets.QPushButton()
        self._config_button.setIcon(QPixmap(":/icons/config_icon"))
        self._config_button.setMinimumSize(30, 30)
        self._config_button.setProperty("class", "borderless")
        self._config_button.clicked.connect(self._config_dialog.show)
        self._line = QtWidgets.QFrame()
        self._line.setObjectName("divisor")
        self._line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self._line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

        self._bar_layout.addWidget(self.account_picker)
        self._bar_layout.addStretch()
        self._bar_layout.addWidget(self._clock)
        self._bar_layout.addStretch()
        self._bar_layout.addWidget(self._config_button)
        self.main_layout.addLayout(self._bar_layout)
        self.main_layout.addWidget(self._line)

        self.setLayout(self.main_layout)
