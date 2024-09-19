"""Dialog to set manage configurations."""

from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.core.password_guard import PasswordGuard
from plutus_terminal.ui.widgets.config.account_config import AccountConfig
from plutus_terminal.ui.widgets.config.news_config import NewsConfig
from plutus_terminal.ui.widgets.config.perps_config import PerpsConfig
from plutus_terminal.ui.widgets.config.terminal_config import TerminalConfig
from plutus_terminal.ui.widgets.config.web3_config import Web3Config


class ConfigDialog(QtWidgets.QDialog):
    """Config dialog."""

    updated_trade_values = Signal()
    leverage_changed = Signal(int)
    update_filters = Signal()
    show_images_toggled = Signal(bool)
    desktop_notifications_toggled = Signal(bool)

    def __init__(
        self,
        pass_guard: PasswordGuard,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize dialog."""
        super().__init__(parent)

        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QtWidgets.QTabWidget()
        self.persp_config = PerpsConfig()
        self.news_config = NewsConfig()
        self.web3_config = Web3Config()
        self.account_config = AccountConfig(pass_guard)
        self.terminal_config = TerminalConfig()

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self.setWindowTitle("Plutus Terminal - Configuration")
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setModal(False)
        self.setMinimumSize(800, 800)

        self._setup_persp_config()
        self.persp_config.updated_trade_values.connect(self.updated_trade_values)
        self.persp_config.leverage_changed.connect(self.leverage_changed)
        self._tab_widget.addTab(self.persp_config, "Trade")

        self.news_config.update_filters.connect(self.update_filters)
        self._tab_widget.addTab(self.news_config, "News Source")

        self._tab_widget.addTab(self.web3_config, "Web3")

        self._tab_widget.addTab(self.account_config, "Account")

        self.terminal_config.show_images_toggled.connect(self.show_images_toggled)
        self.terminal_config.desktop_notifications_toggled.connect(
            self.desktop_notifications_toggled,
        )
        self._tab_widget.addTab(self.terminal_config, "Terminal")

    def _setup_persp_config(self) -> None:
        """Config persp config."""
        self.persp_config.top_bar.hide()

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._tab_widget)
        self.setLayout(self._main_layout)
