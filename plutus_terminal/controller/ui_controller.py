"""Controller to create link between UI and Exchange."""

import logging
from typing import TYPE_CHECKING

import pandas
from PySide6.QtCore import QObject, Signal
from qasync import asyncio, asyncSlot

from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.valid_exchanges import VALID_EXCHANGES
from plutus_terminal.core.news.filter.filter_manager import FilterManager
from plutus_terminal.core.news.news_manager import NewsManager
from plutus_terminal.core.password_guard import PasswordGuard
from plutus_terminal.core.types_ import MessageLevel, UserMessage
from plutus_terminal.message_bus import MessageBus
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase

LOGGER = logging.getLogger(__name__)


class UIController(QObject):
    """Controller to create link between UI and Exchange."""

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
        """Initialize shared variables.

        Args:
            message_bus (MessageBus): Message bus to send signals.
            filter_manager (FilterManager): Filter manager.
            pass_guard (PasswordGuard): Password guard.
            app_config (AppConfig): App config.
        """
        super().__init__()
        self.message_bus = message_bus
        self.news_filter_manager = filter_manager
        self.pass_guard = pass_guard
        self.app_config = app_config
        self.current_timeframe: str = "1"
        self.news_manager: NewsManager
        self.current_exchange: ExchangeBase
        self.current_pair: str

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.message_bus.send_message.connect(self.show_toast_message)

    async def init_async(self) -> None:
        """Initialize async shared variables."""
        keyring_account = self.app_config.current_keyring_account
        self.current_exchange = await VALID_EXCHANGES[str(keyring_account.exchange_name)].create(
            self.message_bus,
            self.pass_guard,
            self.app_config,
        )
        await self.current_exchange.fetch_prices()
        self.current_pair = self.current_exchange.default_pair

        self.news_manager = NewsManager(self.message_bus, self.news_filter_manager, self.pass_guard)
        asyncio.create_task(self.news_manager.fetch_news())

        self.app_config.current_account_id_changed.connect(self.change_current_exchange)

    @property
    def exchange_available_pairs(self) -> set[str]:
        """Get Exchange available pairs."""
        return self.current_exchange.available_pairs

    @asyncSlot()
    async def change_current_exchange(self) -> None:
        """Change current exchange."""
        LOGGER.info("Changing current exchange...")
        self.message_bus.blockSignals(True)
        await self.current_exchange.stop_async()

        keyring_account = self.app_config.current_keyring_account
        self.current_exchange = await VALID_EXCHANGES[str(keyring_account.exchange_name)].create(
            self.message_bus,
            self.pass_guard,
            self.app_config,
        )

        # Init price fetching loops
        await self.current_exchange.fetch_prices()

        if self.current_pair in self.current_exchange.available_pairs:
            await self.change_current_pair(self.current_pair)
        else:
            await self.change_current_pair(self.current_exchange.default_pair)

        self.exchange_changed.emit()
        self.message_bus.blockSignals(False)

    @asyncSlot()
    async def change_current_pair(self, pair: str) -> None:
        """Change current pair.

        Unsubscribe from current pair and subscribe to new pair. Update chart.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
        """
        await self.current_exchange.fetcher.unsubscribe_to_price(self.current_pair)
        await self.current_exchange.fetcher.subscribe_to_price(pair)

        self.current_pair = pair
        self.pair_changed.emit(pair)

    async def fetch_price_history(self) -> tuple[pandas.DataFrame, int]:
        """Fetch price history.

        Returns:
            tuple[pandas.DataFrame, int]: History dataframe and minimal digits.
        """
        history = await self.current_exchange.fetch_price_history(
            self.current_pair,
            self.current_timeframe,
            bars_num=ui_utils.DEFAULT_BAR_NUMBERS,
        )
        history_dataframe = pandas.DataFrame(history)
        minimal_digits = ui_utils.get_minimal_digits(history["low"][0], 4)
        return history_dataframe, minimal_digits

    def update_news_filters(self) -> None:
        """Update news filters."""
        self.news_filter_manager.update_filters()

    async def change_timeframe(self, resolution: str) -> None:
        """Change chart timeframe.

        If timeframe is same as current, do nothing.
        """
        self.current_timeframe = resolution
        self.timeframe_changed.emit(resolution)

    async def fetch_price_history_for_timeframe(self, resolution: str) -> pandas.DataFrame:
        """Fetch price history for timeframe.

        Args:
            resolution (str): Timeframe to fetch.

        Returns:
            pandas.DataFrame: History dataframe.
        """
        history = await self.current_exchange.fetch_price_history(
            self.current_pair,
            resolution,
            bars_num=ui_utils.DEFAULT_BAR_NUMBERS,
        )
        return pandas.DataFrame(history)

    def format_simple_pair_from_pair(self, pair: str) -> str:
        """Format pair to simple pair."""
        return self.current_exchange.format_simple_pair_from_pair(pair)

    async def stop_async(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        LOGGER.debug("Stopping Plutus Terminal async")
        await asyncio.gather(
            self.news_manager.stop_async(),
            self.current_exchange.stop_async(),
        )

    async def set_leverage(self, coin: str, leverage: int) -> None:
        """Set leverage for current pair.

        Args:
            coin (str): Coin to set leverage for.
            leverage (int): Leverage to set.
        """
        try:
            await self.current_exchange.set_leverage(coin, leverage)
        except TransactionFailedError as error:
            Toast.show_message(
                f"Failed to set leverage: {error}",
                type_=ToastType.ERROR,
            )
            return
        pair = self.current_exchange.format_pair_from_coin(coin)
        applied_leverage = self.app_config.leverage
        if leverage < self.current_exchange.min_leverage:
            Toast.show_message(
                f"Leverage of {pair} is too low. Set minimum leverage: {self.current_exchange.min_leverage}x",
                type_=ToastType.WARNING,
            )
        elif leverage > self.current_exchange.max_leverage:
            Toast.show_message(
                f"Leverage of {pair} is too high. Set maximum leverage: {self.current_exchange.max_leverage}x",
                type_=ToastType.WARNING,
            )
        elif applied_leverage != leverage:
            Toast.show_message(
                f"Leverage of {pair} adjusted to: {applied_leverage}x",
                type_=ToastType.WARNING,
            )
        else:
            Toast.show_message(
                f"Leverage of {pair} set to: {applied_leverage}x",
                type_=ToastType.SUCCESS,
            )

    @asyncSlot()
    async def set_all_leverage(self, leverage: int) -> None:
        """Set leverage for all positions.

        Args:
            leverage (int): Leverage to set.
        """
        bounded = max(self.current_exchange.min_leverage, min(self.current_exchange.max_leverage, leverage))
        await self.current_exchange.set_all_leverage(bounded)
        if leverage < self.current_exchange.min_leverage:
            Toast.show_message(
                f"Leverage is too low. Set minimum leverage: {self.current_exchange.min_leverage}x",
                type_=ToastType.WARNING,
            )
        elif leverage > self.current_exchange.max_leverage:
            Toast.show_message(
                f"Leverage is too high. Set maximum leverage: {self.current_exchange.max_leverage}x",
                type_=ToastType.WARNING,
            )
        else:
            Toast.show_message(
                f"Leverage set to all pairs: {bounded}x",
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
        await self.news_manager.stop_async()
        await self.news_manager.fetch_news()
