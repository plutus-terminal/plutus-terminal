"""Plutus terminal main window."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from plutus_terminal import __version__
from plutus_terminal.ui.widgets.account_info import AccountInfo
from plutus_terminal.ui.widgets.config import ConfigDialog
from plutus_terminal.ui.widgets.news_list import NewsList
from plutus_terminal.ui.widgets.perps_trade import PerpsTradeWidget
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.trade_table import TradeTable
from plutus_terminal.ui.widgets.trading_chart import TradingChart
from plutus_terminal.ui.widgets.user_top_bar import UserTopBar

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController

LOGGER = logging.getLogger(__name__)


# TODO: To remove later
def reload_style() -> None:  # noqa: D103
    relative_path = Path(__file__).parent
    with Path.open(relative_path.joinpath("style.qss")) as f:
        QApplication.instance().setStyleSheet(f.read())


class PlutusMainWindow(QMainWindow):
    """Plutus terminal main window."""

    def __init__(self, ui_controller: UIController) -> None:
        """Initialize shared variables."""
        super().__init__()
        self._ui_controller = ui_controller
        self._app_config = ui_controller.app_config

        self.main_layout = QVBoxLayout()
        self.main_widget = QWidget()
        self._work_area_layout = QHBoxLayout()
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_layout = QVBoxLayout()
        self._right_scroll = QScrollArea()

        # Declare classes for visibility
        self.chart: TradingChart
        self._trade_table: TradeTable
        self._account_info: AccountInfo
        self._perps_trade: PerpsTradeWidget
        self._config_dialog: ConfigDialog
        self._user_top_bar: UserTopBar
        self._news_list: NewsList

        # TODO: To remove later
        self.shortcut = QShortcut(QKeySequence("F1"), self)
        self.shortcut.activated.connect(reload_style)

    async def init_async(
        self,
    ) -> None:
        """Initialize async shared variables."""
        # Init config dialog
        self._config_dialog = ConfigDialog(self._ui_controller, parent=self)

        # Init user top bar
        self._user_top_bar = UserTopBar(self._config_dialog, self._ui_controller)

        # Init chart
        self.chart = TradingChart(
            self._ui_controller,
        )

        # Init open trades widget
        self._trade_table = TradeTable(self._ui_controller)

        # Init account info widget
        self._account_info = AccountInfo(
            self._ui_controller,
            parent=self,
        )

        # Init perps trading
        self._perps_trade = PerpsTradeWidget(self._ui_controller)

        # Init news manager
        self._news_list = NewsList(self._ui_controller)
        await self._news_list.fill_old_news()

        await self._setup_widgets()
        self._setup_layout()

    async def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.main_widget.setLayout(self.main_layout)
        self.setWindowTitle(f"Plutus Terminal - {__version__}")
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))

        # Setup account info
        await self._account_info.set_approve_btn_visibility()

        self._right_scroll.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.MinimumExpanding,
        )
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

    def _setup_layout(self) -> None:
        """Organize layouts."""
        self.main_layout.addWidget(self._user_top_bar)

        self._left_splitter.addWidget(self.chart)
        self._left_splitter.addWidget(self._trade_table)
        self._work_area_layout.addWidget(self._left_splitter)
        self._work_area_layout.addWidget(self._news_list)

        self._right_layout.addWidget(self._account_info)
        self._right_layout.addWidget(self._perps_trade)
        self._right_layout.addStretch()
        scroll_widget = QWidget()
        scroll_widget.setLayout(self._right_layout)

        self._right_scroll.setWidget(scroll_widget)
        self._work_area_layout.addWidget(self._right_scroll)

        self.main_layout.addLayout(self._work_area_layout)

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hide window on close."""
        self._ui_controller.app_config.set_gui_settings(
            "window_geometry", self.saveGeometry().data().hex()
        )
        if self._ui_controller.app_config.get_gui_settings("minimize_to_tray"):
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    def show(self) -> None:
        """Override show."""
        self._load_geometry()
        return super().show()

    def _load_geometry(self) -> None:
        """Load window geometry."""
        geometry = self._ui_controller.app_config.get_gui_settings("window_geometry")
        if geometry:
            self.restoreGeometry(bytes.fromhex(geometry))  # type: ignore
