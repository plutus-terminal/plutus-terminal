"""Class to Manage multiple news."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import pandas

from plutus_terminal.core.news.phoenix_news import PhoenixNews
from plutus_terminal.core.news.tree_news import TreeNews

if TYPE_CHECKING:
    from plutus_terminal.core.news.base import NewsFetcher, NewsMessageBus
    from plutus_terminal.core.news.filter.filter_manager import FilterManager
    from plutus_terminal.core.types_ import NewsData

LOGGER = logging.getLogger(__name__)


class NewsManager:
    """Manage multiple news source."""

    def __init__(self, news_bus: NewsMessageBus, filter_manager: FilterManager) -> None:
        """Initialize shared variables.

        Args:
            news_bus (NewsMessageBus): Message bus to send news signals.
            filter_manager (FilterManager): Filter manager to filter news.
        """
        self.news_bus = news_bus
        self.news_sources: list[NewsFetcher] = [TreeNews(), PhoenixNews()]
        self._filter_manager = filter_manager
        self._seen_links: set[str] = set()
        self._news_task: list[asyncio.Task] = []

        self.news_bus.raw_news_signal.connect(self.process_news)

    async def fetch_news(self) -> None:
        """Fetch news from news sources."""
        login_tasks = [news_fetcher.login() for news_fetcher in self.news_sources]
        await asyncio.gather(*login_tasks)
        for news_fetcher in self.news_sources:
            self._news_task.append(
                asyncio.create_task(news_fetcher.subscribe_to_wss(self.news_bus)),
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

        news_data_frame = pandas.DataFrame(old_news)
        news_data_frame["link"] = news_data_frame["link"].str.removesuffix("/")
        news_data_frame = news_data_frame.drop_duplicates(subset="link")
        news_data_frame = news_data_frame.sort_values(by="time", ascending=True)
        # Store displayed news to avoid duplicates
        self._seen_links.update(news_data_frame["link"])

        unique_news: list[NewsData] = news_data_frame.to_dict(orient="records")  # type: ignore

        for news in unique_news:
            self._filter_manager.filter(news)

        return unique_news[len(unique_news) - limit :]

    def process_news(self, raw_news: NewsData) -> None:
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

        # Store displayed news to avoid duplicates
        self._seen_links.add(raw_news["link"])

        raw_news = self._filter_manager.filter(raw_news)

        if LOGGER.isEnabledFor(logging.DEBUG):
            end_time_ms = time.time_ns() / 1000000
            processed_time_ms = end_time_ms - start_time_ms  # type: ignore
            LOGGER.debug(
                "Processed message received. Process time: %f ms message: %s",
                processed_time_ms,
                raw_news,
            )

        self.news_bus.news_signal.emit(raw_news)

    async def stop_async(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        LOGGER.debug("Stopping NewsManager async")
        for news_fetcher in self.news_sources:
            await news_fetcher.stop_async()
