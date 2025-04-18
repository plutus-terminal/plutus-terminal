"""Plutus terminal main window."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas
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
from qasync import asyncSlot

from plutus_terminal import __version__
from plutus_terminal.core.config import CONFIG
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.account_info import AccountInfo
from plutus_terminal.ui.widgets.config import ConfigDialog
from plutus_terminal.ui.widgets.news_list import NewsList
from plutus_terminal.ui.widgets.perps_trade import PerpsTradeWidget
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.trade_table import TradeTable
from plutus_terminal.ui.widgets.trading_chart import TradingChart
from plutus_terminal.ui.widgets.user_top_bar import UserTopBar

if TYPE_CHECKING:
    from lightweight_charts import Chart

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
        self._chart_scroll_polling = False

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
            self.infinite_chart_scroll,
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

        # Set chart data and connect signals
        self._ui_controller.message_bus.subscribed_prices_fetched.connect(
            self.chart.update_chart_tick,
        )
        self._ui_controller.message_bus.positions_fetched.connect(
            self.chart.draw_positions,
        )
        self._ui_controller.message_bus.orders_feched.connect(self.chart.draw_orders)

        # Configure config dialog
        self._config_dialog.updated_trade_values.connect(
            self._update_quick_trade_values,
        )
        self._config_dialog.leverage_changed.connect(
            self._ui_controller.current_exchange.set_all_leverage,
        )
        self._config_dialog.update_filters.connect(self._update_news_filters)
        self._config_dialog.show_images_toggled.connect(self._news_list.show_images_toggled)
        self._config_dialog.desktop_notifications_toggled.connect(
            self._news_list.notifications_toggled,
        )

        # Configure account info
        await self._account_info.set_approve_btn_visibility()
        self._ui_controller.message_bus.balance_fetched.connect(self._account_info.update_balance)

        # Configure Perps Trade
        self._ui_controller.message_bus.subscribed_prices_fetched.connect(
            self._perps_trade.update_liquidation_info,
        )

        # Connect signals for open traders
        self._ui_controller.message_bus.positions_fetched.connect(
            self._trade_table.update_positions,
        )
        self._ui_controller.message_bus.orders_feched.connect(self._trade_table.update_orders)
        self._ui_controller.message_bus.subscribed_prices_fetched.connect(
            self._trade_table.update_prices,
        )
        self._ui_controller.message_bus.formatted_news.connect(self._news_list.add_news)

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
        CONFIG.set_gui_settings("window_geometry", self.saveGeometry().data().hex())
        if CONFIG.get_gui_settings("minimize_to_tray"):
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
        geometry = CONFIG.get_gui_settings("window_geometry")
        if geometry:
            self.restoreGeometry(bytes.fromhex(geometry))

    @asyncSlot()
    async def infinite_chart_scroll(self, chart: Chart, bars_before: int, bars_after: int) -> None:  # noqa: ARG002
        """Function called when chart is scrolled."""
        fetch_threshold = 25
        if bars_before <= fetch_threshold and not self._chart_scroll_polling:
            LOGGER.debug(
                f"Infinite chart scrolling: Fetching more data for {self._ui_controller.current_pair}",
            )
            candle_timestamp = ui_utils.convert_timestamp_from_local_to_utc(
                chart.candle_data["time"].iloc[0],
            )
            self._chart_scroll_polling = True
            history = await self._ui_controller.current_exchange.fetch_price_history(
                self._ui_controller.current_pair,
                self._ui_controller.current_timeframe,
                bars_num=ui_utils.DEFAULT_BAR_NUMBERS * 3,
                to_timestamp=int(candle_timestamp.timestamp()),
            )
            self.chart.update_data(pandas.DataFrame(history))
            self._chart_scroll_polling = False

    def _update_quick_trade_values(self) -> None:
        """Update trade values."""
        self._news_list.update_news_trade_buttons()
        self._perps_trade.update_trade_buttons()
        Toast.show_message("Trade values updated!", type_=ToastType.SUCCESS)

    def _update_news_filters(self) -> None:
        """Update news filters."""
        self._ui_controller.update_news_filters()
        Toast.show_message("News Filters updated", type_=ToastType.SUCCESS)
