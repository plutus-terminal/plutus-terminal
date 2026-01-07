"""Controller for NewsList."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

from plutus_terminal.controller.news_controller import NewsController
from plutus_terminal.ui.widgets.news_widget import NewsWidget

if TYPE_CHECKING:
    from plutus_terminal.core.types_ import NewsData
    from plutus_terminal.controller.ui_controller import UIController


class NewsListController(QObject):
    """Controller for NewsList."""

    add_news_widget = Signal(NewsController, bool)
    clear_list = Signal()
    update_trade_buttons = Signal()

    def __init__(self, ui_controller: UIController) -> None:
        """Initialize controller.

        Args:
            ui_controller (UIController): UI Controller.
        """
        super().__init__()
        self.ui_controller = ui_controller
        self.app_config = ui_controller.app_config
        self.exchange = ui_controller.current_exchange
        self.news_manager = ui_controller.news_manager
        self.max_news = 25

        self.active_news_controllers: list[NewsController] = []

    def connect_signals(self) -> None:
        """Connect signals."""
        self.ui_controller.message_bus.formatted_news.connect(self.on_new_news)
        self.ui_controller.exchange_changed.connect(self.on_exchange_changed)

        self.app_config.trade_value_high_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_low_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_lowest_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_high_changed.connect(self.update_trade_buttons.emit)

    def on_new_news(self, news_data: NewsData) -> None:
        """Handle new news.

        Args:
            news_data (NewsData): News data.
        """
        # Do not add ignored news
        if news_data["ignored"]:
            return

        # Notification logic is handled in View or here?
        # The View handled SFX and Toasts. We can emit a signal for that.

        self._create_and_emit_widget(news_data, display_delay=True)

    @asyncSlot()
    async def fill_old_news(self) -> None:
        """Fetch and fill old news."""
        self.clear_list.emit()
        self.active_news_controllers.clear() # Should we stop them? They shouldn't have active timers anyway.

        list_news = await self.news_manager.fetch_old_news(self.max_news)
        for news_data in list_news:
            if news_data["ignored"]:
                continue
            self._create_and_emit_widget(news_data, display_delay=False)

    def _create_and_emit_widget(self, news_data: NewsData, display_delay: bool) -> None:
        """Create controller and emit to view.

        Args:
            news_data (NewsData): News data.
            display_delay (bool): Whether to display delay.
        """
        controller = NewsController(
            news_data,
            self.exchange,
            self.app_config,
            self.exchange.available_pairs
        )
        self.active_news_controllers.append(controller)

        # Cleanup logic
        if len(self.active_news_controllers) > self.max_news:
            # Remove oldest controller to prevent memory leak
            self.active_news_controllers.pop(0)

        self.add_news_widget.emit(controller, display_delay)
        controller.create_interactions()

    @asyncSlot()
    async def on_exchange_changed(self) -> None:
        """Handle exchange change."""
        self.exchange = self.ui_controller.current_exchange
        await self.fill_old_news()
        self.update_trade_buttons.emit()

    async def set_max_news(self, max_news: int) -> None:
        """Set max news.

        Args:
            max_news (int): Max news count.
        """
        self.max_news = max_news
        await self.fill_old_news()
