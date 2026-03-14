# ruff: noqa: S101
"""Tests for live news update handling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QCoreApplication

from plutus_terminal.core.news.base import default_message_key, merge_news_update
from plutus_terminal.core.news.news_manager import NewsManager
from plutus_terminal.message_bus import MessageBus

if TYPE_CHECKING:
    from plutus_terminal.core.news.types import NewsData


def _ensure_qt_app() -> QCoreApplication:
    """Create a Qt core app once for signal-based tests."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class _FilterManagerStub:
    """Minimal filter manager stub."""

    def filter(self, news_data: NewsData) -> NewsData:
        """Return news unchanged."""
        return news_data


class _FetcherStub:
    """Minimal news fetcher stub with update support."""

    NEWS_SERVICE_NAME = "PhoenixNews"

    async def subscribe_to_wss(self, message_bus: MessageBus) -> None:
        """Unused in tests."""
        _ = message_bus

    async def fetch_old_news(self, limit: int) -> list[NewsData]:  # noqa: ARG002
        """Unused in tests."""
        return []

    def get_message_key(self, news_data: NewsData) -> str:
        """Return the stable key for a message."""
        return default_message_key(news_data)

    def merge_update(self, current_news: NewsData, incoming_news: NewsData) -> NewsData:
        """Merge a partial update into a full news item."""
        return merge_news_update(current_news, incoming_news)

    async def stop_async(self) -> None:
        """Unused in tests."""


def _make_news(**overrides: object) -> NewsData:
    """Build a NewsData payload for tests."""
    news_data: NewsData = {
        "news_id": "",
        "title": "Original title",
        "link": "https://example.com/news",
        "body": "Original body",
        "image": "",
        "is_quote": False,
        "quote_message": "",
        "quote_user": "",
        "quote_image": "",
        "is_reply": False,
        "is_self_reply": False,
        "reply_user": "",
        "reply_message": "",
        "reply_image": "",
        "is_retweet": False,
        "retweet_user": "",
        "icon": "",
        "source": "Phoenix",
        "time": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "coin": set(),
        "feed": "PhoenixNews",
        "sfx": ":/sfx/coin",
        "is_update": False,
        "update_type": "",
        "applied_updates": set(),
        "summary_title": "",
        "summary_body": "",
        "is_important": False,
        "ignored": False,
    }
    news_data.update(overrides)
    return news_data


class TestNewsManagerUpdates:
    """Tests for same-ID live news updates."""

    def test_process_news_merges_same_id_updates(self) -> None:
        """Same-ID updates should emit an update event instead of a new item."""
        _ensure_qt_app()
        message_bus = MessageBus()
        manager = NewsManager(message_bus, _FilterManagerStub(), object())
        manager.news_sources = [_FetcherStub()]
        manager._news_sources_by_name = {  # noqa: SLF001
            manager.news_sources[0].NEWS_SERVICE_NAME: manager.news_sources[0],
        }

        added_news: list[NewsData] = []
        updated_news: list[NewsData] = []
        message_bus.formatted_news.connect(added_news.append)
        message_bus.formatted_news_updated.connect(updated_news.append)

        async def _exercise() -> None:
            await manager.process_news(
                _make_news(news_id="phoenix-1", link="https://example.com/news/"),
            )
            await manager.process_news(
                _make_news(
                    news_id="phoenix-1",
                    link="",
                    time=datetime(2026, 3, 8, 0, 0, 5, tzinfo=timezone.utc),
                    is_update=True,
                    update_type="summary-ai",
                    summary_title="AI summary title",
                    summary_body="AI summary body",
                ),
            )

        asyncio.run(_exercise())

        assert len(added_news) == 1
        assert len(updated_news) == 1
        assert added_news[0]["link"] == "https://example.com/news"
        assert updated_news[0]["news_id"] == "phoenix-1"
        assert updated_news[0]["body"] == "Original body"
        assert updated_news[0]["summary_title"] == "AI summary title"
        assert updated_news[0]["summary_body"] == "AI summary body"
        assert updated_news[0]["applied_updates"] == {"summary-ai"}
        assert updated_news[0]["time"] == datetime(2026, 3, 8, tzinfo=timezone.utc)

    def test_process_news_ignores_update_before_original(self) -> None:
        """Partial updates without a cached original should be dropped."""
        _ensure_qt_app()
        message_bus = MessageBus()
        manager = NewsManager(message_bus, _FilterManagerStub(), object())
        manager.news_sources = [_FetcherStub()]
        manager._news_sources_by_name = {  # noqa: SLF001
            manager.news_sources[0].NEWS_SERVICE_NAME: manager.news_sources[0],
        }

        updated_news: list[NewsData] = []
        message_bus.formatted_news_updated.connect(updated_news.append)

        async def _exercise() -> None:
            await manager.process_news(
                _make_news(
                    news_id="phoenix-1",
                    link="",
                    is_update=True,
                    update_type="important-auto",
                    is_important=True,
                ),
            )

        asyncio.run(_exercise())

        assert updated_news == []

    def test_fetch_old_news_merges_same_id_update_packets(self) -> None:
        """Historical Phoenix updates should merge into the original news item."""
        _ensure_qt_app()
        message_bus = MessageBus()
        manager = NewsManager(message_bus, _FilterManagerStub(), object())

        class _HistoricalFetcherStub(_FetcherStub):
            async def fetch_old_news(self, limit: int) -> list[NewsData]:  # noqa: ARG002
                return [
                    _make_news(news_id="phoenix-1"),
                    _make_news(
                        news_id="phoenix-1",
                        link="",
                        time=datetime(2026, 3, 8, 0, 0, 5, tzinfo=timezone.utc),
                        is_update=True,
                        update_type="summary-ai",
                        applied_updates={"summary-ai"},
                        summary_title="AI summary title",
                        summary_body="AI summary body",
                    ),
                    _make_news(
                        news_id="phoenix-1",
                        link="",
                        time=datetime(2026, 3, 8, 0, 0, 10, tzinfo=timezone.utc),
                        is_update=True,
                        update_type="important-auto",
                        applied_updates={"important-auto"},
                        is_important=True,
                    ),
                ]

        manager.news_sources = [_HistoricalFetcherStub()]
        manager._news_sources_by_name = {  # noqa: SLF001
            manager.news_sources[0].NEWS_SERVICE_NAME: manager.news_sources[0],
        }

        historical_news = asyncio.run(manager.fetch_old_news(10))

        assert len(historical_news) == 1
        assert historical_news[0]["news_id"] == "phoenix-1"
        assert historical_news[0]["summary_title"] == "AI summary title"
        assert historical_news[0]["summary_body"] == "AI summary body"
        assert historical_news[0]["is_important"] is True
        assert historical_news[0]["applied_updates"] == {"important-auto", "summary-ai"}

    def test_merge_news_update_handles_missing_existing_coin_set(self) -> None:
        """Merge coin updates defensively when the cached payload has a null coin field."""
        current_news = _make_news(coin=cast("Any", None))
        incoming_news = _make_news(is_update=True, update_type="coins", coin={"BTC", "ETH"})

        merged_news = merge_news_update(current_news, incoming_news)

        assert merged_news["coin"] == {"BTC", "ETH"}
