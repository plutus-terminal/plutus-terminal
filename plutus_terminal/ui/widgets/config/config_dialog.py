"""Dialog to set manage configurations."""

from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.controller.ui_controller import UIController
from plutus_terminal.ui.widgets.config.account_config import AccountConfig
from plutus_terminal.ui.widgets.config.news_config import NewsConfig
from plutus_terminal.ui.widgets.config.perps_config import PerpsConfig
from plutus_terminal.ui.widgets.config.terminal_config import TerminalConfig
from plutus_terminal.ui.widgets.config.web3_config import Web3Config


class ConfigDialog(QtWidgets.QDialog):
    """Config dialog."""

    def __init__(
        self,
        ui_controller: UIController,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize dialog."""
        super().__init__(parent)

        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QtWidgets.QTabWidget()
        self.persp_config = PerpsConfig(ui_controller)
        self.news_config = NewsConfig(ui_controller)
        self.web3_config = Web3Config()
        self.account_config = AccountConfig(ui_controller.pass_guard, ui_controller.app_config)
        self.terminal_config = TerminalConfig(ui_controller.app_config)

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self.setWindowTitle("Plutus Terminal - Configuration")
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setModal(False)
        self.setMinimumSize(800, 800)

        self._setup_persp_config()
        self._tab_widget.addTab(self.persp_config, "Trade")

        self._tab_widget.addTab(self.news_config, "News Source")

        self._tab_widget.addTab(self.web3_config, "Web3")

        self._tab_widget.addTab(self.account_config, "Account")

        self._tab_widget.addTab(self.terminal_config, "Terminal")

    def _setup_persp_config(self) -> None:
        """Config persp config."""
        self.persp_config.top_bar.hide()

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._tab_widget)
        self.setLayout(self._main_layout)
