"""Dialog to set manage configurations."""

from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.ui.widgets.config.account_config import AccountConfig
from plutus_terminal.ui.widgets.config.news_config import NewsConfig
from plutus_terminal.ui.widgets.config.perps_config import PerpsConfig
from plutus_terminal.ui.widgets.config.web3_config import Web3Config


class ConfigDialog(QtWidgets.QDialog):
    """Config dialog."""

    updated_trade_values = Signal()
    leverage_changed = Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize dialog."""
        super().__init__(parent)

        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QtWidgets.QTabWidget()
        self.persp_config = PerpsConfig()
        self.news_config = NewsConfig()
        self.web3_config = Web3Config()
        self.account_config = AccountConfig()

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

        self._tab_widget.addTab(self.news_config, "News Source")

        self._tab_widget.addTab(self.web3_config, "Web3")

        self._tab_widget.addTab(self.account_config, "Account")

    def _setup_persp_config(self) -> None:
        """Config persp config."""
        self.persp_config.top_bar.hide()

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._tab_widget)
        self.setLayout(self._main_layout)

    def on_new_account(self) -> None:
        """Update info based on new account."""
        self.persp_config.on_new_account()
