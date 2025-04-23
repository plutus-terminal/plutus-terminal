"""Protocols and base class for news fetching."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from plutus_terminal.core.types_ import NewsData
    from plutus_terminal.message_bus import MessageBus


class NewsFetcher(Protocol):
    """News fetcher protocol."""

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

    async def login(self) -> None:
        """Login to news source."""
        ...

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        ...
