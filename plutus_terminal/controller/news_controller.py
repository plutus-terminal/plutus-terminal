"""Controller for NewsWidget."""

from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QPixmap, QPixmapCache
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
import re2  # type: ignore

from plutus_terminal.core.exceptions import InvalidOrderSizeError
from plutus_terminal.core.exchange.types import PerpsTradeType
from plutus_terminal.core.types_ import NewsData, PerpsTradeDirection
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from plutus_terminal.core.config import AppConfig
    from plutus_terminal.core.exchange.base import ExchangeBase, ExchangeFetcher

ICON_MAP = {
    "blogs": ":/sources/blog",
    "usgov": ":/sources/usgov",
    "binance en": ":/sources/binance",
    "bybit": ":/sources/bybit",
    "upbit": ":/sources/upbit",
    "telegram": ":/sources/telegram",
    "crypto": ":/sources/crypto",
    "webs": ":/sources/webs",
    "medium": ":/sources/medium",
    "terminal": ":/sources/terminal",
    "synopticstreams": ":/sources/synoptic",
    "onchain": ":/sources/on_chain",
}

NEWS_TIME_COLORS = {
    "green": 10,
    "yellow": 20,
}


class NewsController(QObject):
    """Controller for NewsWidget."""

    # Signals to update the View
    update_icon = Signal(QPixmap)
    update_timer = Signal(str, str)  # text, style_class
    timer_finished = Signal()
    update_price_percent = Signal(str, str, str)  # pair, text, color_style
    update_initial_price = Signal(str, str) # pair, price_text
    show_interaction_widgets = Signal(str) # pair
    update_trade_buttons = Signal()

    def __init__(
        self,
        news_data: NewsData,
        exchange: ExchangeBase,
        app_config: AppConfig,
        available_pairs: set[str],
    ) -> None:
        """Initialize controller.

        Args:
            news_data (NewsData): News data.
            exchange (ExchangeBase): Exchange instance.
            app_config (AppConfig): App config.
            available_pairs (set[str]): Available pairs.
        """
        super().__init__()
        self.news_data = news_data
        self.exchange = exchange
        self.app_config = app_config
        self.available_pairs = available_pairs

        self._async_tasks: list[asyncio.Task] = []
        self._max_time = 60
        self._elapsed_time = 0
        self._price_change: dict[str, str] = {}
        self._initial_prices: dict[str, float] = {}
        self._re_percent_complied = re2.compile(r"\(([^)]+)%\)")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_on_timer)

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.app_config.trade_value_high_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_low_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_lowest_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_high_changed.connect(self.update_trade_buttons.emit)

    def load_icon(self) -> None:
        """Load icon for the news."""
        source = self.news_data["source"].lower()
        if source == "twitter":
            icon_pixmap = QPixmap()
            QPixmapCache.find(self.news_data["icon"], icon_pixmap)

            if not icon_pixmap:
                icon_pixmap = QPixmap(":/icons/no_token")
                # Need to handle network request.
                # Since QNetworkAccessManager needs a parent, we can use self (QObject)
                # But typically it's better if the View handles the network request or we pass the manager?
                # Actually, Controller is a QObject, so it can own QNAM.
                network_manager = QNetworkAccessManager(self)
                network_manager.finished.connect(self._on_icon_downloaded)
                network_manager.get(QNetworkRequest(QUrl(self.news_data["icon"])))

            self.update_icon.emit(icon_pixmap)
        else:
            icon_pixmap = QPixmap()
            QPixmapCache.find(source, icon_pixmap)
            if not icon_pixmap:
                icon_pixmap = QPixmap(ICON_MAP.get(source, ":/icons/no_token"))
                QPixmapCache.insert(source, icon_pixmap)
            self.update_icon.emit(icon_pixmap)

    def _on_icon_downloaded(self, reply: QNetworkReply) -> None:
        """Handle downloaded icon.

        Args:
            reply (QNetworkReply): Network reply.
        """
        image_data = reply.readAll()
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        QPixmapCache.insert(self.news_data["icon"], pixmap)
        self.update_icon.emit(pixmap)

    def open_link(self) -> None:
        """Open news link."""
        QDesktopServices.openUrl(self.news_data["link"])

    def create_interactions(self) -> bool:
        """Setup interactions logic.

        Returns:
            bool: True if interactions created.
        """
        interaction_created = False
        interaction_pairs = set()

        for coin in self.news_data["coin"]:
            pair = self.exchange.format_pair_from_coin(coin)
            if pair not in self.available_pairs:
                continue

            interaction_pairs.add(pair)
            self.show_interaction_widgets.emit(coin) # Notify view to create/show widgets for this coin
            interaction_created = True

        if interaction_created:
             # Set price of news at source time
            self._async_tasks.append(
                asyncio.create_task(
                    self.set_initial_prices(self.exchange.fetcher.fetch_price_at_time),
                ),
            )

            if self.news_data["time"].timestamp() > time.time() - 60:
                for pair in interaction_pairs:
                    self._async_tasks.append(
                        asyncio.create_task(self.exchange.fetcher.subscribe_to_price(pair)),
                    )

                self.exchange.message_bus.subscribed_prices_fetched.connect(
                    self.update_percents,
                )
                self.timer_finished.connect(
                    partial(
                        self.exchange.message_bus.subscribed_prices_fetched.disconnect,
                        self.update_percents,
                    ),
                )
                self.timer_finished.connect(
                    partial(
                        self._unsubscribe_from_price_updates,
                        interaction_pairs,
                        self.exchange.fetcher,
                    ),
                )

                self.start_timer()

        return interaction_created

    def start_timer(self) -> None:
        """Start the timer."""
        self.timer.start(1000)

    def _update_on_timer(self) -> None:
        """Update timer logic."""
        self._elapsed_time += 1

        style_class = "danger"
        if self._elapsed_time < NEWS_TIME_COLORS["green"]:
            style_class = "success"
        elif self._elapsed_time < NEWS_TIME_COLORS["yellow"]:
            style_class = "warning"

        self.update_timer.emit(str(self._elapsed_time), style_class)

        # Update percent labels
        for pair in self._initial_prices:
            try:
                price_change = self._price_change.get(pair, "(0.00%)")
                percent_change = self._re_percent_complied.search(price_change)
                color_style = "color: red;"
                if float(percent_change.group(1)) > 0:  # type: ignore
                    color_style = "color: rgb(100, 255, 100);"

                self.update_price_percent.emit(pair, price_change, color_style)
            except KeyError:
                continue

        if self._elapsed_time >= self._max_time:
            self.timer.stop()
            self.timer_finished.emit()

    async def set_initial_prices(self, fetch_price_at_time) -> None:
        """Set initial prices.

        Args:
            fetch_price_at_time (Callable): Function to fetch price.
        """
        for coin in self.news_data["coin"]:
            pair = self.exchange.format_pair_from_coin(coin)
            if pair in self.available_pairs:
                current_price = await fetch_price_at_time(
                    pair,
                    self.news_data["time"].timestamp(),
                )
                current_price = current_price["price"]
                self._initial_prices[pair] = current_price
                minimal_digits = ui_utils.get_minimal_digits(current_price, 4)

                text = f"Price at news: {current_price:,.{minimal_digits}f}"
                self.update_initial_price.emit(pair, text)

    def update_percents(self, cached_prices: dict) -> None:
        """Update cached percents.

        Args:
            cached_prices (dict): Cached prices.
        """
        for pair, initial_price in self._initial_prices.items():
            pair_data = cached_prices.get(pair, {"price": initial_price})
            current_price = pair_data["price"]
            percentage = ((current_price / initial_price) - 1) * 100
            minimal_digits = ui_utils.get_minimal_digits(current_price, 4)
            self._price_change[pair] = (
                f"{current_price:,.{minimal_digits}f} ({round(percentage, 3):.3f}%)"
            )

    def _unsubscribe_from_price_updates(
        self,
        pairs: set[str],
        exchange_fetcher: ExchangeFetcher,
    ) -> None:
        """Unsubscribe.

        Args:
            pairs (set[str]): Pairs to unsubscribe.
            exchange_fetcher (ExchangeFetcher): Exchange fetcher.
        """
        for pair in pairs:
            self._async_tasks.append(
                asyncio.create_task(exchange_fetcher.unsubscribe_to_price(pair)),
            )

    def handle_interaction_click(
        self,
        coin: str,
        config_key_value: str,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
    ) -> None:
        """Handle interaction click.

        Args:
            coin (str): Coin name.
            config_key_value (str): Config key for value.
            trade_direction (PerpsTradeDirection): Direction.
            trade_type (PerpsTradeType): Type.
        """
        amount = getattr(self.app_config, config_key_value)
        pair = self.exchange.format_pair_from_coin(coin)
        try:
            # We need to run this async. Since we are in sync context (button click),
            # we should create a task.
            asyncio.create_task(self.exchange.create_order(pair, amount, trade_direction, trade_type))
        except InvalidOrderSizeError as error:
            Toast.show_message(
                f"{error}",
                type_=ToastType.ERROR,
            )

    def get_trade_value(self, index: int) -> int:
        """Get trade value from config.

        Args:
            index (int): Index of button.

        Returns:
            int: Trade value.
        """
        value_map = {
            0: self.app_config.trade_value_lowest,
            1: self.app_config.trade_value_low,
            2: self.app_config.trade_value_medium,
            3: self.app_config.trade_value_high,
        }
        return value_map.get(index, 0)

    def stop(self):
        """Cleanup."""
        self.timer.stop()
        # Cancel tasks if needed
