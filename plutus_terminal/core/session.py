"""Session model to hold domain data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, Signal
from qasync import asyncio, asyncSlot

from plutus_terminal.core import utils
from plutus_terminal.core.exchange.valid_exchanges import VALID_EXCHANGES
from plutus_terminal.core.news.filter.filter_manager import FilterManager
from plutus_terminal.core.news.news_manager import NewsManager

if TYPE_CHECKING:
    import pandas
    from plutus_terminal.core.config import AppConfig
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)


class Session(QObject):
    """Session model to hold domain data."""

    exchange_changed = Signal()
    pair_changed = Signal(str)
    timeframe_changed = Signal(str)

    def __init__(
        self,
        message_bus: MessageBus,
        filter_manager: FilterManager,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> None:
        """Initialize session."""
        super().__init__()
        self.message_bus = message_bus
        self.news_filter_manager = filter_manager
        self.pass_guard = pass_guard
        self.app_config = app_config
        self.current_timeframe: str = "1"
        self.news_manager: Optional[NewsManager] = None
        self.current_exchange: Optional[ExchangeBase] = None
        self.current_pair: str = ""

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
        if self.current_exchange:
            return self.current_exchange.available_pairs
        return set()

    @asyncSlot()
    async def change_current_exchange(self) -> None:
        """Change current exchange."""
        LOGGER.info("Changing current exchange...")
        self.message_bus.blockSignals(True)
        if self.current_exchange:
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
        """Change current pair."""
        if self.current_exchange:
            await self.current_exchange.fetcher.unsubscribe_to_price(self.current_pair)
            await self.current_exchange.fetcher.subscribe_to_price(pair)

        self.current_pair = pair
        self.pair_changed.emit(pair)

    async def change_timeframe(self, resolution: str) -> None:
        """Change chart timeframe."""
        self.current_timeframe = resolution
        self.timeframe_changed.emit(resolution)

    async def fetch_price_history(self) -> tuple[pandas.DataFrame, int]:
        """Fetch price history."""
        if not self.current_exchange:
            return pandas.DataFrame(), 0
        history = await self.current_exchange.fetch_price_history(
            self.current_pair,
            self.current_timeframe,
            bars_num=utils.DEFAULT_BAR_NUMBERS,
        )
        history_dataframe = pandas.DataFrame(history)
        minimal_digits = utils.get_minimal_digits(history["low"][0], 4)
        return history_dataframe, minimal_digits

    async def fetch_price_history_for_timeframe(self, resolution: str) -> pandas.DataFrame:
        """Fetch price history for timeframe."""
        if not self.current_exchange:
            return pandas.DataFrame()
        history = await self.current_exchange.fetch_price_history(
            self.current_pair,
            resolution,
            bars_num=utils.DEFAULT_BAR_NUMBERS,
        )
        return pandas.DataFrame(history)

    def format_simple_pair_from_pair(self, pair: str) -> str:
        """Format pair to simple pair."""
        if self.current_exchange:
            return self.current_exchange.format_simple_pair_from_pair(pair)
        return pair

    async def stop_async(self) -> None:
        """Stop all async tasks."""
        LOGGER.debug("Stopping Session async")
        tasks = []
        if self.news_manager:
            tasks.append(self.news_manager.stop_async())
        if self.current_exchange:
            tasks.append(self.current_exchange.stop_async())
        await asyncio.gather(*tasks)
