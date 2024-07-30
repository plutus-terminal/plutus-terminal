"""Widget to display news data and interact with news."""

from __future__ import annotations

import asyncio
from functools import partial
import time
from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QMouseEvent, QPixmap, QPixmapCache
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
import re2  # type: ignore

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import InvalidOrderSizeError
from plutus_terminal.core.exchange.types import PerpsTradeType
from plutus_terminal.core.types_ import NewsData, PerpsTradeDirection
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.image_web_viewer import ImageWebViewer
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from collections.abc import Callable
    from decimal import Decimal

    from plutus_terminal.core.exchange.base import ExchangeBase, ExchangeFetcher

ICON_MAP = {
    "blogs": ":/sources/blog",
    "usgov": ":/sources/usgov",
    "binance en": ":/sources/binance",
    "upbit": ":/sources/upbit",
    "telegram": ":/sources/telegram",
    "crypto": ":/sources/crypto",
    "webs": ":/sources/webs",
    "medium": ":/sources/medium",
    "terminal": ":/sources/terminal",
}

NEWS_TIME_COLORS = {
    "green": 10,
    "yellow": 20,
}


class NewsWidget(QtWidgets.QGroupBox):
    """Widget to display news data and interact with news."""

    news_clicked = Signal(object)
    pair_clicked = Signal(str)
    timer_end = Signal()

    def __init__(
        self,
        news_data: NewsData,
        format_to_pair: Callable,
        available_pairs: set,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared variables."""
        super().__init__(parent=parent)
        self.news_data = news_data
        self.format_to_pair = format_to_pair
        self._available_pairs = available_pairs
        self._show_images = True
        self._re_percent_complied = re2.compile(r"\(([^)]+)%\)")
        self._async_tasks: list[asyncio.Task] = []

        self._max_time = 60
        self._elapsed_time = 0
        self._price_change: dict[str, str] = {}
        self._initial_prices: dict[str, Decimal] = {}
        self._icon_scale = 50

        self.main_layout = QtWidgets.QHBoxLayout()
        self.icon_layout = QtWidgets.QVBoxLayout()
        self.icon_label = QtWidgets.QLabel()
        self.info_layout = QtWidgets.QVBoxLayout()
        self.title_layout = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel()
        self.timer = QTimer(self)
        self.stop_watch_label = QtWidgets.QLabel()
        self.body_frame = QtWidgets.QFrame()
        self.body_layout = QtWidgets.QVBoxLayout()
        self.body_label = QtWidgets.QLabel()
        self.body_image = ImageWebViewer()
        self.quote_icon_up = QtWidgets.QLabel()
        self.quote_frame = QtWidgets.QFrame()
        self.quote_layout = QtWidgets.QVBoxLayout()
        self.quote_title_layout = QtWidgets.QHBoxLayout()
        self.quote_title = QtWidgets.QLabel()
        self.quote_label = QtWidgets.QLabel()
        self.quote_image = ImageWebViewer()
        self.metadata_layout = QtWidgets.QHBoxLayout()
        self.time_label = QtWidgets.QLabel()
        self.feed_label = QtWidgets.QLabel()
        self.source_label = QtWidgets.QLabel()
        self.link_button = QtWidgets.QPushButton()
        self.coin_label = QtWidgets.QLabel()
        self.interactions_layout = QtWidgets.QVBoxLayout()

        self.group_box_layout: dict[str, QtWidgets.QVBoxLayout] = {}
        self.percent_label: dict[str, QtWidgets.QLabel] = {}

        self._setup_widgets()
        self._set_news_icon()
        self._setup_layout()

    @property
    def show_images(self) -> bool:
        """Return if images should be shown."""
        return self._show_images

    @show_images.setter
    def show_images(self, value: bool) -> None:
        """Set if images should be shown."""
        self._show_images = value
        if self.news_data["image"]:
            self.body_image.setVisible(value)
        if self.news_data["quote_image"]:
            self.quote_image.setVisible(value)

    def _setup_widgets(self) -> None:  # noqa: PLR0915
        """Create internal widgets."""
        self.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.icon_label.setFixedSize(self._icon_scale, self._icon_scale)
        self.icon_label.setScaledContents(True)
        self.icon_label.setObjectName("newsIcon")

        self.title_label.setObjectName("title")
        self.title_label.setText(self.news_data["title"])
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )

        self.stop_watch_label.hide()
        self.stop_watch_label.setObjectName("newsStopWatch")
        self.stop_watch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stop_watch_label.setMaximumWidth(50)
        self.stop_watch_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        self.body_frame.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self.body_frame.setObjectName("newsFrameBody")

        if self.news_data["body"] or self.news_data["image"]:
            self.body_label.setObjectName("newsBody")
            self.body_label.setTextFormat(Qt.TextFormat.RichText)
            self.body_label.setText(self.news_data["body"])
            self.body_label.setWordWrap(True)
            self.body_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse,
            )

            if self.news_data["image"]:
                self.body_image.set_image(self.news_data["image"])
            else:
                self.body_image.deleteLater()
        else:
            self.body_frame.hide()
            self.body_label.hide()

        if self.news_data["is_quote"] and any(
            (self.news_data["quote"], self.news_data["quote_image"]),
        ):
            quote_up_pixmap = QPixmap()
            QPixmapCache.find("quotes_up", quote_up_pixmap)
            if not quote_up_pixmap:
                quote_up_pixmap = QPixmap(":/icons/double_quote_up")
                QPixmapCache.insert("quotes_up", quote_up_pixmap)
            self.quote_icon_up.setPixmap(quote_up_pixmap)
            self.quote_icon_up.setAlignment(Qt.AlignmentFlag.AlignLeft)

            self.quote_frame.setFrameStyle(QtWidgets.QFrame.Shape.Box)
            self.quote_frame.setObjectName("newsFrameQuote")

            self.quote_title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.quote_title.setObjectName("subTitle")
            self.quote_title.setText(self.news_data["quoter"])

            self.quote_label.setObjectName("newsQuote")
            self.quote_label.setTextFormat(Qt.TextFormat.RichText)
            self.quote_label.setText(self.news_data["quote"])
            self.quote_label.setWordWrap(True)
            self.quote_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse,
            )

            if self.news_data["quote_image"]:
                self.quote_image.set_image(self.news_data["quote_image"])
            else:
                self.quote_image.deleteLater()
        else:
            self.quote_frame.hide()

        self.link_button.setObjectName("newsLink")
        self.link_button.setFlat(True)
        self.link_button.setIcon(QPixmap(":/icons/external_link"))
        self.link_button.setIconSize(QSize(25, 25))
        self.link_button.setFixedSize(25, 25)
        self.link_button.clicked.connect(self.open_link)

        self.time_label.setObjectName("newsTime")
        self.time_label.setText(
            f'Source Time: {self.news_data["time"].strftime("%H:%M:%S:%f")}',
        )
        self.time_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )
        self.time_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )

        self.feed_label.setObjectName("newsFeed")
        self.feed_label.setText(f"Feed: {self.news_data['feed']}")
        self.feed_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )
        self.feed_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )

        self.source_label.setObjectName("newsFeed")
        self.source_label.setText(f"Source: {self.news_data['source']}")
        self.source_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        )
        self.source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )

        if self.news_data["coin"]:
            self.coin_label.setObjectName("newsCoin")
            self.coin_label.setText(f"Suggestions: {', '.join(self.news_data['coin'])}")

        self.setFixedWidth(500)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

    def _set_news_icon(self) -> None:
        """Set icon to news, fetch from the internet if source is twitter."""
        source = self.news_data["source"].lower()
        if source == "twitter":
            icon_pixmap = QPixmap()
            # Try to get from cache if available
            QPixmapCache.find(self.news_data["icon"], icon_pixmap)

            # If not in cache, set temp icon and fetch from internet
            if not icon_pixmap:
                icon_pixmap = QPixmap(":/icons/no_token")
                network_manager = QNetworkAccessManager(self)
                network_manager.finished.connect(
                    partial(self._set_network_icon, self.icon_label),
                )
                network_manager.get(QNetworkRequest(QUrl(self.news_data["icon"])))
        else:
            icon_pixmap = QPixmap()
            QPixmapCache.find(source, icon_pixmap)
            if not icon_pixmap:
                icon_pixmap = QPixmap(ICON_MAP.get(source, ":/icons/no_token"))
                QPixmapCache.insert(source, icon_pixmap)

        self.icon_label.setPixmap(icon_pixmap)

    def _set_network_icon(self, target_label: QtWidgets.QLabel, reply: QNetworkReply) -> None:
        """Set icon pixmap from network reply."""
        image_data = reply.readAll()
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        QPixmapCache.insert(self.news_data["icon"], pixmap)
        target_label.setPixmap(pixmap)

    def _setup_layout(self) -> None:
        """Connect widgets to layouts."""
        self.main_layout.addLayout(self.icon_layout)
        self.icon_layout.addWidget(self.icon_label)
        self.icon_layout.addWidget(self.stop_watch_label)
        self.icon_layout.addStretch()

        self.main_layout.addLayout(self.info_layout)
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addWidget(self.time_label)
        self.info_layout.addLayout(self.title_layout)

        self.body_frame.setLayout(self.body_layout)
        self.body_layout.addWidget(self.body_label)
        self.body_layout.addWidget(self.body_image)
        self.body_layout.addWidget(self.quote_label)
        self.body_layout.addWidget(self.quote_frame)

        self.quote_frame.setLayout(self.quote_layout)
        self.quote_title_layout.addWidget(self.quote_icon_up)
        self.quote_title_layout.addWidget(self.quote_title)
        self.quote_layout.addLayout(self.quote_title_layout)
        self.quote_layout.addWidget(self.quote_label)
        self.quote_layout.addWidget(self.quote_image)

        self.info_layout.addWidget(self.body_frame)
        self.metadata_layout.addWidget(self.feed_label)
        self.metadata_layout.addWidget(self.source_label)
        self.metadata_layout.addWidget(self.link_button)
        self.info_layout.addLayout(self.metadata_layout)
        self.info_layout.addWidget(self.coin_label)

        self.info_layout.addLayout(self.interactions_layout)

        self.setLayout(self.main_layout)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit signal when clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.news_clicked.emit(self)
        return super().mousePressEvent(event)

    async def set_initial_prices(self, fetch_price_at_time: Callable) -> None:
        """Set initial prices for coins in data."""
        for coin in self.news_data["coin"]:
            pair = self.format_to_pair(coin)
            if pair in self._available_pairs:
                current_price = await fetch_price_at_time(
                    pair,
                    self.news_data["time"].timestamp(),
                )
                current_price = current_price["price"]
                self._initial_prices[pair] = current_price
                minimal_digits = ui_utils.get_minimal_digits(current_price, 4)
                initial_price_label = QtWidgets.QLabel(
                    f"Price at news: {current_price:,.{minimal_digits}f}",
                )
                percent_layout = self.group_box_layout[coin].itemAt(0).layout()
                percent_layout.insertWidget(1, initial_price_label)  # type: ignore

    def create_interactions(self, exchange: ExchangeBase) -> bool:  # noqa: PLR0915
        """Create buttons for interactions.

        Args:
            exchange (ExchangeBase): Exchange instance.

        Returns:
            bool: If an interaction was created.
        """
        interaction_created = False
        interaction_pairs = set()
        for coin in self.news_data["coin"]:
            pair = self.format_to_pair(coin)

            if pair not in self._available_pairs:
                continue
            interaction_pairs.add(pair)

            button_group_box = ClickableGroupBox(coin)
            button_group_box.clicked.connect(partial(self.pair_clicked.emit, pair))
            self.group_box_layout[coin] = QtWidgets.QVBoxLayout()
            self.percent_label[pair] = QtWidgets.QLabel("0%")
            self.percent_label[pair].hide()
            button_layout = QtWidgets.QGridLayout()

            percent_layout = QtWidgets.QHBoxLayout()
            percent_layout.addWidget(self.percent_label[pair])
            self.group_box_layout[coin].addLayout(percent_layout)
            self.group_box_layout[coin].addLayout(button_layout)
            button_group_box.setLayout(self.group_box_layout[coin])

            option_keys = (
                "trade_value_lowest",
                "trade_value_low",
                "trade_value_medium",
                "trade_value_high",
            )
            for index, option_key in enumerate(option_keys):
                value = getattr(
                    CONFIG,
                    option_key,
                )
                button_long = QtWidgets.QPushButton(f"${value}")
                button_long.setObjectName(f"LONG_{index}")
                button_long.setMinimumHeight(25)
                button_long.clicked.connect(
                    partial(
                        self.handle_interaction_click,
                        exchange.create_order,
                        pair,
                        option_key,
                        PerpsTradeDirection.LONG,
                        PerpsTradeType.MARKET,
                    ),
                )
                button_long.setProperty("class", "LONG")
                match index:
                    case 0:
                        button_layout.addWidget(button_long, 0, 0)
                    case 1:
                        button_layout.addWidget(button_long, 0, 1)
                    case 2:
                        button_layout.addWidget(button_long, 1, 0)
                    case 3:
                        button_layout.addWidget(button_long, 1, 1)

            for index, option_key in enumerate(option_keys):
                value = getattr(
                    CONFIG,
                    option_key,
                )
                button_short = QtWidgets.QPushButton(f"-${value}")
                button_short.setObjectName(f"SHORT_{index}")
                button_short.setMinimumHeight(25)
                button_short.clicked.connect(
                    partial(
                        self.handle_interaction_click,
                        exchange.create_order,
                        pair,
                        option_key,
                        PerpsTradeDirection.SHORT,
                        PerpsTradeType.MARKET,
                    ),
                )
                button_short.setProperty("class", "SHORT")
                match index:
                    case 0:
                        button_layout.addWidget(button_short, 0, 2)
                    case 1:
                        button_layout.addWidget(button_short, 0, 3)
                    case 2:
                        button_layout.addWidget(button_short, 1, 2)
                    case 3:
                        button_layout.addWidget(button_short, 1, 3)

            self.interactions_layout.addWidget(button_group_box)
            interaction_created = True

        if interaction_created:
            # Set price of news at source time
            self._async_tasks.append(
                asyncio.create_task(
                    self.set_initial_prices(exchange.fetcher.fetch_price_at_time),
                ),
            )

            if self.news_data["time"].timestamp() > time.time() - 60:
                for pair in interaction_pairs:
                    self.percent_label[pair].show()
                    self._async_tasks.append(
                        asyncio.create_task(exchange.fetcher.subscribe_to_price(pair)),
                    )

                exchange.fetcher_bus.subscribed_prices_signal.connect(
                    self.update_percents,
                )
                self.timer_end.connect(
                    partial(
                        exchange.fetcher_bus.subscribed_prices_signal.disconnect,
                        self.update_percents,
                    ),
                )
                self.timer_end.connect(
                    partial(
                        self._unsubscribe_from_price_updates,
                        interaction_pairs,
                        exchange.fetcher,
                    ),
                )

                self.start_timer()
        return interaction_created

    def handle_interaction_click(
        self,
        trade_function: Callable,
        coin: str,
        config_key_value: str,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
    ) -> None:
        """Handle buys/sells from interaction buttons.

        This will ensure that the amount is updated dynamically at button press.

        Args:
            trade_function (Callable): Trade function.
            coin (str): Coin to trade.
            config_key_value (str): Config key value to get amount from.
            trade_direction (PerpsTradeDirection): Trade direction.
            trade_type (PerpsTradeType): Trade type.
        """
        amount = getattr(CONFIG, config_key_value)
        try:
            trade_function(coin, amount, trade_direction, trade_type)
        except InvalidOrderSizeError as error:
            Toast.show_message(
                f"{error}",
                type_=ToastType.ERROR,
            )

    def _unsubscribe_from_price_updates(
        self,
        pairs: set[str],
        exchange_fetcher: ExchangeFetcher,
    ) -> None:
        """Unsubscribe from price updates.

        Args:
            pairs (set[str]): Pairs to unsubscribe.
            exchange_fetcher (ExchangeFetcher): Exchange fetcher.
        """
        for pair in pairs:
            self._async_tasks.append(
                asyncio.create_task(exchange_fetcher.unsubscribe_to_price(pair)),
            )

    def start_timer(self) -> None:
        """Start time for each 1 second."""
        self.timer.timeout.connect(self._update_on_timer)
        self.stop_watch_label.setVisible(True)
        self.timer.start(1000)

    def _update_on_timer(self) -> None:
        """Update label with time."""
        self._elapsed_time += 1
        if self._elapsed_time < NEWS_TIME_COLORS["green"]:
            self.stop_watch_label.setProperty("class", "success")
            self.stop_watch_label.style().polish(self.stop_watch_label)
        elif self._elapsed_time < NEWS_TIME_COLORS["yellow"]:
            self.stop_watch_label.setProperty("class", "warning")
            self.stop_watch_label.style().polish(self.stop_watch_label)
        else:
            self.stop_watch_label.setProperty("class", "danger")
            self.stop_watch_label.style().polish(self.stop_watch_label)

        self.stop_watch_label.setText(str(self._elapsed_time))
        for pair in self._initial_prices:
            try:
                price_change = self._price_change.get(pair, "(0.00%)")
                percent_change = self._re_percent_complied.search(price_change)
                # Slice to get digits only
                if float(percent_change.group(1)) > 0:  # type: ignore
                    self.percent_label[pair].setStyleSheet("color: rgb(100, 255, 100);")
                else:
                    self.percent_label[pair].setStyleSheet("color: red;")
                self.percent_label[pair].setText(price_change)
            except KeyError:
                continue

        if self._elapsed_time >= self._max_time:
            self.timer.stop()
            self.stop_watch_label.setVisible(False)
            for pair in self._initial_prices:
                try:
                    self.percent_label[pair].hide()
                except KeyError:
                    continue
            self.timer_end.emit()

    def update_percents(self, cached_prices: dict) -> None:
        """Update percents labels for tokens."""
        for pair, initial_price in self._initial_prices.items():
            # In case the websocket reply is a bit late
            pair_data = cached_prices.get(pair, {"price": initial_price})
            current_price = pair_data["price"]
            percentage = ((current_price / initial_price) - 1) * 100
            minimal_digits = ui_utils.get_minimal_digits(current_price, 4)
            self._price_change[pair] = (
                f"{current_price:,.{minimal_digits}f} ({round(percentage, 3):.3f}%)"
            )

    def set_selected_style(self) -> None:
        """Set border to selected style."""
        self.setProperty("class", "selected")
        self.style().polish(self)

    def set_unselected_style(self) -> None:
        """Set border to unselected style."""
        self.setProperty("class", "unselected")
        self.style().polish(self)

    def open_link(self) -> None:
        """Open link in browser."""
        QDesktopServices.openUrl(self.news_data["link"])

    def update_trade_buttons(self) -> None:
        """Update trade values."""
        value_map = {
            0: CONFIG.trade_value_lowest,
            1: CONFIG.trade_value_low,
            2: CONFIG.trade_value_medium,
            3: CONFIG.trade_value_high,
        }
        for index in range(4):
            for widget in self.findChildren(QtWidgets.QPushButton, f"SHORT_{index}"):
                widget.setText(f"-${value_map[index]}")
            for widget in self.findChildren(QtWidgets.QPushButton, f"LONG_{index}"):
                widget.setText(f"${value_map[index]}")


class ClickableGroupBox(QtWidgets.QGroupBox):
    """GroupBox clickable."""

    clicked = Signal()

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(title, parent=parent)
        self.installEventFilter(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit signal when clicked."""
        self.clicked.emit()
        return super().mousePressEvent(event)
