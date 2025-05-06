"""Class to Manage multiple news."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextlib import suppress
import logging
import time
from typing import TYPE_CHECKING

from qasync import asyncSlot

from plutus_terminal.core.news.phoenix_news import PhoenixNews
from plutus_terminal.core.news.synoptic_news import SynopticNews
from plutus_terminal.core.news.tree_news import TreeNews

if TYPE_CHECKING:
    from plutus_terminal.core.news.base import NewsFetcher
    from plutus_terminal.core.news.filter.filter_manager import FilterManager
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.core.types_ import NewsData
    from plutus_terminal.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)


class NewsManager:
    """Manage multiple news source."""

    _SEEN_CACHE_MAX = 10_000

    def __init__(
        self,
        message_bus: MessageBus,
        filter_manager: FilterManager,
        pass_guard: PasswordGuard,
    ) -> None:
        """Initialize shared variables.

        Args:
            message_bus (MessageBus): Message bus to send news signals.
            filter_manager (FilterManager): Filter manager to filter news.
            pass_guard (PasswordGuard): Password guard
        """
        self.message_bus = message_bus
        self._filter_manager = filter_manager
        self._pass_guard = pass_guard
        self.news_sources: list[NewsFetcher] = [
            TreeNews(self._pass_guard),
            PhoenixNews(self._pass_guard),
            SynopticNews(self._pass_guard),
        ]
        self._seen_links: OrderedDict[str, None] = OrderedDict()
        self._async_lock = asyncio.Lock()
        self._news_task: list[asyncio.Task] = []

        self.message_bus.raw_news.connect(self.process_news)

    async def fetch_news(self) -> None:
        """Fetch news from news sources."""
        for news_fetcher in self.news_sources:
            self._news_task.append(
                asyncio.create_task(
                    news_fetcher.subscribe_to_wss(self.message_bus),
                    name=news_fetcher.NEWS_SERVICE_NAME,
                ),
            )

    async def fetch_old_news(self, limit: int) -> list[NewsData]:
        """Fetch old news from all news sources.

        Remove duplicate news from sources.

        Args:
            limit (int): Number of news to fetch.

        Returns:
            list[NewsData]: List of old news.
        """
        LOGGER.debug("Fetching old news from all news sources, limit: %s", limit)

        old_news: list[NewsData] = []
        tasks = [news_fetcher.fetch_old_news(limit) for news_fetcher in self.news_sources]
        old_news_results = await asyncio.gather(*tasks)

        # Flatten the list of lists into a single list
        old_news = [item for sublist in old_news_results for item in sublist]

        unique: list[NewsData] = []

        for item in old_news:
            link = item["link"].removesuffix("/")
            if link and link not in self._seen_links:
                self._seen_links[link] = None
                unique.append(item)

        for news in unique:
            self._filter_manager.filter(news)

        return unique[len(unique) - limit :]

    @asyncSlot()
    async def process_news(self, raw_news: NewsData) -> None:
        """Process raw news.

        Validate if news is not a duplicate and add extra suggestions based on map.

        Args:
            raw_news (NewsData): News to process.
        """
        if LOGGER.isEnabledFor(logging.DEBUG):
            start_time_ms = time.time_ns() / 1000000

        # Strip trailing slash to ensre that link is not duplicated
        raw_news["link"] = raw_news["link"].removesuffix("/")

        # Check if news is already displayed based on link
        if raw_news["link"] in self._seen_links:
            LOGGER.debug("Duplicate news received: %s", raw_news["link"])
            return

        async with self._async_lock:
            # Store displayed news to avoid duplicates
            if raw_news["link"]:
                self._seen_links[raw_news["link"]] = None

            if len(self._seen_links) > self._SEEN_CACHE_MAX:
                self._seen_links.popitem(last=False)

        raw_news = self._filter_manager.filter(raw_news)

        self.message_bus.formatted_news.emit(raw_news)

        if LOGGER.isEnabledFor(logging.DEBUG):
            end_time_ms = time.time_ns() / 1000000
            processed_time_ms = end_time_ms - start_time_ms  # type: ignore
            LOGGER.debug(
                "Processed message received. Process time: %f ms message: %s",
                processed_time_ms,
                raw_news,
            )

    async def stop_async(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        LOGGER.debug("Stopping NewsManager async")
        for task in self._news_task:
            task.cancel()

        with suppress(asyncio.CancelledError):
            await asyncio.gather(*self._news_task, return_exceptions=True)

        for news_fetcher in self.news_sources:
            await news_fetcher.stop_async()
