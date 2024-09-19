"""Plutus terminal main window."""

from __future__ import annotations

import asyncio
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

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exchange.base import (
    LOGGER,
    ExchangeBase,
    ExchangeFetcherMessageBus,
)
from plutus_terminal.core.exchange.valid_exchanges import VALID_EXCHANGES
from plutus_terminal.core.news.base import NewsMessageBus
from plutus_terminal.core.news.filter.filter_manager import FilterManager
from plutus_terminal.core.news.news_manager import NewsManager
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.account_info import AccountInfo
from plutus_terminal.ui.widgets.config import ConfigDialog
from plutus_terminal.ui.widgets.news_list import NewsList
from plutus_terminal.ui.widgets.options_widget import OptionsWidget
from plutus_terminal.ui.widgets.perps_trade import PerpsTradeWidget
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.trade_table import TradeTable
from plutus_terminal.ui.widgets.trading_chart import TradingChart
from plutus_terminal.ui.widgets.user_top_bar import UserTopBar

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import KeyringAccount
    from plutus_terminal.core.password_guard import PasswordGuard


# TODO: To remove later
def reload_style() -> None:  # noqa: D103
    relative_path = Path(__file__).parent
    with Path.open(relative_path.joinpath("style.qss")) as f:
        QApplication.instance().setStyleSheet(f.read())


class PlutusTerminal(QMainWindow):
    """Plutus terminal main window."""

    def __init__(self, pass_guard: PasswordGuard) -> None:
        """Initialize shared variables."""
        super().__init__()
        self._pass_guard = pass_guard
        self._fetcher_message_bus = ExchangeFetcherMessageBus()
        self._news_message_bus = NewsMessageBus()
        self._async_tasks = []

        self.main_layout = QVBoxLayout()
        self.main_widget = QWidget()
        self._work_area_layout = QHBoxLayout()
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_layout = QVBoxLayout()
        self._right_scroll = QScrollArea()

        # Declare classes for visibility
        self._current_exchange: ExchangeBase
        self._current_pair: str
        self._chart: TradingChart
        self._trade_table: TradeTable
        self._account_info: AccountInfo
        self._perps_trade: PerpsTradeWidget
        self._config_dialog: ConfigDialog
        self._user_top_bar: UserTopBar
        self._news_manager: NewsManager
        self._filter_manager: FilterManager
        self._news_list: NewsList
        self._options_widget: OptionsWidget

        # TODO: To remove later
        self.shortcut = QShortcut(QKeySequence("F1"), self)
        self.shortcut.activated.connect(reload_style)

    async def init_async(self) -> None:
        """Initialize async shared variables."""
        self._config_dialog = ConfigDialog(self._pass_guard, parent=self)

        self._user_top_bar = UserTopBar(self._config_dialog, self._pass_guard)
        self._user_top_bar.account_picker.account_changed.connect(self.change_account)

        # Start current exchange loops
        keyring_account: KeyringAccount = self._user_top_bar.account_picker.currentData()
        self._current_exchange = await VALID_EXCHANGES[str(keyring_account.exchange_name)].create(
            self._fetcher_message_bus,
            self._pass_guard,
        )
        self._async_tasks.append(asyncio.create_task(self._current_exchange.fetch_prices()))
        self._current_pair = self._current_exchange.default_pair

        self._chart = TradingChart(
            self._current_exchange.available_pairs,
            self._current_exchange.format_simple_pair_from_pair,
        )

        # Init open trades widget
        self._trade_table = TradeTable(self._current_exchange)

        # Init account info widget
        self._account_info = AccountInfo(
            self._current_exchange.account_info,
            self._current_exchange.is_ready_to_trade,
            self._current_exchange.approve_for_trading,
            parent=self,
        )

        # Init perps trading
        self._perps_trade = PerpsTradeWidget(self._current_exchange)

        # Init filter manager
        self._filter_manager = FilterManager()

        # Init news manager
        self._news_manager = NewsManager(self._news_message_bus, self._filter_manager)
        self._async_tasks.append(asyncio.create_task(self._news_manager.fetch_news()))
        self._news_list = NewsList(self._current_exchange)

        # Init options Widget
        self._options_widget = OptionsWidget(self._current_exchange)
        if not self._current_exchange.has_options():
            self._options_widget.setEnabled(False)
            self._options_widget.setVisible(False)

        await self._setup_widgets()
        self._setup_layout()

        self._exchange_update_affected = [
            widget for widget in self.findChildren(QWidget) if hasattr(widget, "on_new_exchange")
        ]
        self._account_update_affected = [
            widget for widget in self.findChildren(QWidget) if hasattr(widget, "on_new_account")
        ]

    async def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.main_widget.setLayout(self.main_layout)
        self.setWindowTitle("Plutus Terminal")
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))

        # Set chart data and connect signals
        await self._set_chart_timeframe("1")
        self._chart.current_pair = self._current_pair
        self._chart.timeframe_signal.connect(self._set_chart_timeframe)
        self._fetcher_message_bus.subscribed_prices_signal.connect(
            self._chart.update_chart_tick,
        )
        self._chart.pair_changed.connect(self._change_current_pair)
        self._fetcher_message_bus.positions_signal.connect(
            self._chart.draw_positions,
        )
        self._fetcher_message_bus.orders_signal.connect(self._chart.draw_orders)

        # Configure config dialog
        self._config_dialog.updated_trade_values.connect(
            self._update_quick_trade_values,
        )
        self._config_dialog.leverage_changed.connect(
            self._current_exchange.set_all_leverage,
        )
        self._config_dialog.update_filters.connect(self._update_news_filters)
        self._config_dialog.show_images_toggled.connect(self._news_list.show_images_toggled)
        self._config_dialog.desktop_notifications_toggled.connect(
            self._news_list.notifications_toggled,
        )

        # Configure account info
        await self._account_info.set_approve_btn_visibility()
        self._fetcher_message_bus.balance_signal.connect(self._account_info.update_balance)

        # Configure Perps Trade
        self._perps_trade.pair_changed.connect(self._change_current_pair)
        self._fetcher_message_bus.subscribed_prices_signal.connect(
            self._perps_trade.update_liquidation_info,
        )

        # Connect signals for open traders
        self._fetcher_message_bus.positions_signal.connect(
            self._trade_table.update_positions,
        )
        self._fetcher_message_bus.orders_signal.connect(self._trade_table.update_orders)
        self._fetcher_message_bus.subscribed_prices_signal.connect(
            self._trade_table.update_prices,
        )
        self._trade_table.pair_clicked.connect(self._change_current_pair)

        self._news_list.pair_clicked.connect(self._change_current_pair)
        self._news_list.refresh_news.connect(self._fill_news_list)
        await self._fill_news_list()
        self._news_message_bus.news_signal.connect(self._news_list.add_news)

        self._right_scroll.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.MinimumExpanding,
        )
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self._options_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._options_widget.setMinimumWidth(400)

    def _setup_layout(self) -> None:
        """Organize layouts."""
        self.main_layout.addWidget(self._user_top_bar)

        self._left_splitter.addWidget(self._chart)
        self._left_splitter.addWidget(self._trade_table)
        self._work_area_layout.addWidget(self._left_splitter)
        self._work_area_layout.addWidget(self._news_list)

        self._right_layout.addWidget(self._account_info)
        self._right_layout.addWidget(self._perps_trade)
        self._right_layout.addWidget(self._options_widget)
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
    async def _change_current_pair(self, pair: str) -> None:
        """Change current pair.

        Unsubscribe from current pair and subscribe to new pair. Update chart.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
        """
        # Do nothing if pair is same as current
        if pair == self._current_pair:
            return

        # Disconnect signal to avoid visual glitch
        self._fetcher_message_bus.subscribed_prices_signal.disconnect(
            self._chart.update_chart_tick,
        )
        self._fetcher_message_bus.positions_signal.disconnect(
            self._chart.draw_positions,
        )
        self._fetcher_message_bus.orders_signal.disconnect(self._chart.draw_orders)

        await self._current_exchange.fetcher.unsubscribe_to_price(self._current_pair)
        await self._current_exchange.fetcher.subscribe_to_price(pair)

        self._current_pair = pair
        self._chart.current_pair = pair

        history = await self._current_exchange.fetch_price_history(
            pair,
            self._chart.current_timeframe,
            bars_num=200,
        )
        history_dataframe = pandas.DataFrame(history)
        self._chart.set_start_data(history_dataframe, reset=True)
        minimal_digits = ui_utils.get_minimal_digits(history["low"][0], 4)
        self._chart.main_chart.precision(minimal_digits)

        await self._perps_trade.update_current_pair(pair)

        self._fetcher_message_bus.subscribed_prices_signal.connect(
            self._chart.update_chart_tick,
        )
        self._fetcher_message_bus.positions_signal.connect(
            self._chart.draw_positions,
        )
        self._fetcher_message_bus.orders_signal.connect(self._chart.draw_orders)

    @asyncSlot()
    async def _set_chart_timeframe(self, resolution: str) -> None:
        """Set chart timeframe."""
        history = await self._current_exchange.fetch_price_history(
            self._current_pair,
            resolution,
            bars_num=200,
        )
        history_dataframe = pandas.DataFrame(history)
        self._chart.set_start_data(history_dataframe)

    @asyncSlot()
    async def _fill_news_list(self) -> None:
        """Fill news list with old news."""
        self._news_list.setDisabled(True)
        old_news = await self._news_manager.fetch_old_news(self._news_list.max_news)
        self._news_list.fill_old_news(old_news)
        self._news_list.setDisabled(False)

    @asyncSlot()
    async def change_account(self, account: KeyringAccount) -> None:
        """Chage current account.

        Update exchangeBase on all modules of the list
        _exchange_update_affected and account_update_affected
        with the on_new_exchange and on_new_account.

        Args:
            account (KeyringAccount): Account to switch to.
        """
        toast_id = Toast.show_message(
            "Changing account...",
            type_=ToastType.WARNING,
            timeout=20000,
        )
        self.setEnabled(False)
        new_exchange = VALID_EXCHANGES[str(account.exchange_name)]
        await self.on_new_exchange(new_exchange)
        self.setEnabled(True)
        Toast.update_message(
            toast_id,
            "Account changed successfully!",
            ToastType.SUCCESS,
        )

    def _update_quick_trade_values(self) -> None:
        """Update trade values."""
        self._news_list.update_news_trade_buttons()
        self._perps_trade.update_trade_buttons()
        Toast.show_message("Trade values updated!", type_=ToastType.SUCCESS)

    def _update_news_filters(self) -> None:
        """Update news filters."""
        self._filter_manager.update_filters()
        Toast.show_message("News Filters updated", type_=ToastType.SUCCESS)

    async def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update exchangeBase on all modules of the list exchange_update_affected."""
        await self._current_exchange.stop_async()

        self._news_message_bus.blockSignals(True)
        self._fetcher_message_bus.blockSignals(True)

        self._current_exchange = await new_exchange.create(
            self._fetcher_message_bus,
            self._pass_guard,
        )

        # Init price fetching loops
        self._current_pair = self._current_exchange.default_pair
        self._async_tasks.append(asyncio.create_task(self._current_exchange.fetch_prices()))

        # Update modules with new exchange
        for module in self._exchange_update_affected:
            LOGGER.debug("Setting up new exchange: %s", module)
            module.blockSignals(True)
            module.on_new_exchange(self._current_exchange)  # type: ignore
            module.blockSignals(False)

        # Enable options if available
        self._options_widget.setEnabled(self._current_exchange.has_options())
        self._options_widget.setVisible(self._current_exchange.has_options())

        # Rebuild news list
        await self._fill_news_list()

        # Update chart
        await self._set_chart_timeframe(self._chart.current_timeframe)

        # reload config from database
        CONFIG.load_config()

        # Update account info
        self._account_info.approve_btn.setVisible(
            not await self._current_exchange.is_ready_to_trade(),
        )

        for module in self._account_update_affected:
            module.blockSignals(True)
            module.on_new_account()  # type: ignore
            module.blockSignals(False)

        self._news_message_bus.blockSignals(False)
        self._fetcher_message_bus.blockSignals(False)

        await self._current_exchange.fetcher.resubscribe_on_going_connections()
        self._update_quick_trade_values()

    async def stop_async(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        LOGGER.debug("Stopping Plutus Terminal async")
        for task in self._async_tasks:
            task.cancel()
        await asyncio.gather(
            self._news_manager.stop_async(),
            self._current_exchange.stop_async(),
        )
