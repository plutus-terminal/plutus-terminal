"""Protocols and base class for news fetching."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from plutus_terminal.core.news.types import NewsData
    from plutus_terminal.message_bus import MessageBus


def default_message_key(news_data: NewsData) -> str:
    """Build a stable key for deduplicating and updating news messages."""
    return news_data["news_id"] or news_data["link"]


def merge_news_update(current_news: NewsData, incoming_news: NewsData) -> NewsData:
    """Merge a partial update packet into a full news payload."""
    merged_news = deepcopy(cast("dict[str, object]", current_news))

    for key, value in incoming_news.items():
        if key == "time":
            continue

        if key == "coin":
            if value:
                merged_news[key] = set(cast("set[str]", merged_news["coin"])) | set(
                    cast("set[str]", value),
                )
            continue

        if isinstance(value, bool):
            merged_news[key] = bool(merged_news.get(key, False)) or value
            continue

        if value not in ("", set()):
            merged_news[key] = value

    merged_news["is_update"] = False
    return cast("NewsData", merged_news)


class NewsFetcher(Protocol):
    """News fetcher protocol."""

    NEWS_SERVICE_NAME: str

    async def subscribe_to_wss(self, message_bus: MessageBus) -> None:
        """Subscribe to news wss and emit news signal on new entry.

        Args:
            message_bus (plutus_terminal.message_bus.MessageBus): Message bus
                to emit news messages
        """
        ...

    async def fetch_old_news(self, limit: int) -> list[NewsData]:
        """Fetch old news from API.

        Args:
            limit (int): Amount of news to fetch.

        Returns:
            list[NewsData]: List of old news. This list is expected to be ordered.
            from latest to oldest.
        """
        ...

    def get_message_key(self, news_data: NewsData) -> str:
        """Return the stable key used to deduplicate and update messages."""
        ...

    def merge_update(self, current_news: NewsData, incoming_news: NewsData) -> NewsData:
        """Merge a partial update packet into the current full news payload."""
        ...

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        ...
