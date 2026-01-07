"""Controller to create link between UI and Exchange."""

import logging
from typing import TYPE_CHECKING, Optional

import pandas
from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

from plutus_terminal.core import utils
from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.news.filter.filter_manager import FilterManager
from plutus_terminal.core.news.news_manager import NewsManager
from plutus_terminal.core.password_guard import PasswordGuard
from plutus_terminal.core.session import Session
from plutus_terminal.core.types_ import MessageLevel, UserMessage
from plutus_terminal.message_bus import MessageBus
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase

LOGGER = logging.getLogger(__name__)


class UIController(QObject):
    """Controller to create link between UI and Exchange.

    Acts as a facade/adapter for Session to keep backward compatibility.
    """

    exchange_changed = Signal()
    """Signal to notify about exchange change."""

    pair_changed = Signal(str)
    """Signal to notify about pair change.

    Args:
        pair (str): Pair.
    """

    timeframe_changed = Signal(str)
    """Signal to notify about timeframe change.

    Args:
        timeframe (str): Timeframe.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        filter_manager: FilterManager,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> None:
        """Initialize shared variables."""
        super().__init__()
        self.message_bus = message_bus
        self.news_filter_manager = filter_manager
        self.pass_guard = pass_guard
        self.app_config = app_config

        # Initialize Session
        self.session = Session(message_bus, filter_manager, pass_guard, app_config)

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.message_bus.send_message.connect(self.show_toast_message)

        # Forward Session signals
        self.session.exchange_changed.connect(self.exchange_changed.emit)
        self.session.pair_changed.connect(self.pair_changed.emit)
        self.session.timeframe_changed.connect(self.timeframe_changed.emit)

    async def init_async(self) -> None:
        """Initialize async shared variables."""
        await self.session.init_async()

    @property
    def current_exchange(self) -> Optional["ExchangeBase"]:
        """Get current exchange from session."""
        return self.session.current_exchange

    @current_exchange.setter
    def current_exchange(self, value: "ExchangeBase") -> None:
        """Set current exchange in session."""
        self.session.current_exchange = value

    @property
    def current_pair(self) -> str:
        """Get current pair from session."""
        return self.session.current_pair

    @current_pair.setter
    def current_pair(self, value: str) -> None:
        """Set current pair in session."""
        self.session.current_pair = value

    @property
    def current_timeframe(self) -> str:
        """Get current timeframe from session."""
        return self.session.current_timeframe

    @current_timeframe.setter
    def current_timeframe(self, value: str) -> None:
        """Set current timeframe in session."""
        self.session.current_timeframe = value

    @property
    def news_manager(self) -> Optional[NewsManager]:
        """Get news manager from session."""
        return self.session.news_manager

    @property
    def exchange_available_pairs(self) -> set[str]:
        """Get Exchange available pairs."""
        return self.session.exchange_available_pairs

    @asyncSlot()
    async def change_current_exchange(self) -> None:
        """Change current exchange."""
        await self.session.change_current_exchange()

    @asyncSlot()
    async def change_current_pair(self, pair: str) -> None:
        """Change current pair."""
        await self.session.change_current_pair(pair)

    async def fetch_price_history(self) -> tuple[pandas.DataFrame, int]:
        """Fetch price history."""
        return await self.session.fetch_price_history()

    def update_news_filters(self) -> None:
        """Update news filters."""
        self.news_filter_manager.update_filters()

    async def change_timeframe(self, resolution: str) -> None:
        """Change chart timeframe."""
        await self.session.change_timeframe(resolution)

    async def fetch_price_history_for_timeframe(self, resolution: str) -> pandas.DataFrame:
        """Fetch price history for timeframe."""
        return await self.session.fetch_price_history_for_timeframe(resolution)

    def format_simple_pair_from_pair(self, pair: str) -> str:
        """Format pair to simple pair."""
        return self.session.format_simple_pair_from_pair(pair)

    async def stop_async(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        await self.session.stop_async()

    async def set_leverage(self, coin: str, leverage: int) -> None:
        """Set leverage for current pair.

        Args:
            coin (str): Coin to set leverage for.
            leverage (int): Leverage to set.
        """
        if not self.session.current_exchange:
            return

        await self.session.current_exchange.set_leverage(self.session.current_pair, leverage)
        pair = self.session.current_exchange.format_pair_from_coin(coin)
        if leverage < self.session.current_exchange.min_leverage:
            Toast.show_message(
                f"Leverage of {pair} is too low. Set minimum leverage: {self.session.current_exchange.min_leverage}x",
                type_=ToastType.WARNING,
            )
        elif leverage > self.session.current_exchange.max_leverage:
            Toast.show_message(
                f"Leverage of {pair} is too high. Set maximum leverage: {self.session.current_exchange.max_leverage}x",
                type_=ToastType.WARNING,
            )
        else:
            Toast.show_message(
                f"Leverage of {pair} set to: {leverage}x",
                type_=ToastType.SUCCESS,
            )

    @asyncSlot()
    async def set_all_leverage(self, leverage: int) -> None:
        """Set leverage for all positions.

        Args:
            leverage (int): Leverage to set.
        """
        if not self.session.current_exchange:
            return

        await self.session.current_exchange.set_all_leverage(leverage)
        if leverage < self.session.current_exchange.min_leverage:
            Toast.show_message(
                f"Leverage is too low. Set minimum leverage: {self.session.current_exchange.min_leverage}x",
                type_=ToastType.WARNING,
            )
        elif leverage > self.session.current_exchange.max_leverage:
            Toast.show_message(
                f"Leverage is too high. Set maximum leverage: {self.session.current_exchange.max_leverage}x",
                type_=ToastType.WARNING,
            )
        else:
            Toast.show_message(
                f"Leverage set to all pairs: {leverage}x",
                type_=ToastType.SUCCESS,
            )

    def show_toast_message(self, message: UserMessage) -> None:
        """Handle user message.

        Send Toast message.

        Args:
            message (UserMessage): User message.
        """
        level_map = {
            MessageLevel.INFO: ToastType.MESSAGE,
            MessageLevel.SUCCESS: ToastType.SUCCESS,
            MessageLevel.WARNING: ToastType.WARNING,
            MessageLevel.ERROR: ToastType.ERROR,
        }

        Toast.show_message(
            message=message.text,
            timeout=message.timeout_ms,
            desktop=message.desktop,
            type_=level_map[message.level],
            message_id=message.message_id,
        )

    @asyncSlot()
    async def restart_news_manager(self) -> None:
        """Force news login."""
        if self.session.news_manager:
            await self.session.news_manager.stop_async()
            await self.session.news_manager.fetch_news()
