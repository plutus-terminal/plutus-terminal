# ruff: noqa: S101
"""Tests for Phoenix same-ID update payload parsing."""

from __future__ import annotations

from datetime import datetime, timezone

from plutus_terminal.core.news.phoenix_news import PhoenixNews


class TestPhoenixNewsUpdates:
    """Tests for Phoenix update message parsing."""

    def test_format_news_keeps_inline_ai_fields_on_historical_news(self) -> None:
        """Historical Phoenix news should keep inline AI summary and important fields."""
        phoenix_news = PhoenixNews(object())

        news_data = phoenix_news.format_news(
            {
                "_id": "68b05cb3b7ec4e1ed10f3861",
                "createdAt": "2026-03-08T16:42:11.227Z",
                "source": "Twitter",
                "username": "phoenix_news",
                "body": "Historical news body",
                "url": "https://example.com/news",
                "summaryAI": "Short summary",
                "cryptoAI": "Long summary",
                "importantAuto": True,
            },
        )

        assert news_data["news_id"] == "68b05cb3b7ec4e1ed10f3861"
        assert news_data["is_update"] is False
        assert news_data["summary_title"] == "Short summary"
        assert news_data["summary_body"] == "Long summary"
        assert news_data["is_important"] is True
        assert news_data["applied_updates"] == set()
        assert news_data["time"] == datetime(2026, 3, 8, 16, 42, 11, 227000, tzinfo=timezone.utc)

    def test_format_news_parses_summary_update_payload(self) -> None:
        """Phoenix summary updates should be treated as partial updates."""
        phoenix_news = PhoenixNews(object())

        news_data = phoenix_news.format_news(
            {
                "_id": "68b05cb3b7ec4e1ed10f3861",
                "noticeId": "815396d948",
                "time": 1756388531227,
                "type": "summary-ai",
                "summaryAI": "Short summary",
                "cryptoAI": "Long summary",
            },
        )

        assert news_data["news_id"] == "68b05cb3b7ec4e1ed10f3861"
        assert news_data["is_update"] is True
        assert news_data["update_type"] == "summary-ai"
        assert news_data["applied_updates"] == {"summary-ai"}
        assert news_data["summary_title"] == "Short summary"
        assert news_data["summary_body"] == "Long summary"
        assert news_data["body"] == ""

    def test_format_news_parses_important_auto_payload(self) -> None:
        """Phoenix important-auto updates should preserve the stable news ID."""
        phoenix_news = PhoenixNews(object())

        news_data = phoenix_news.format_news(
            {
                "_id": "67557d0374b91122ef77c7c9",
                "noticeId": "302876",
                "time": 1734042346123,
                "type": "important-auto",
                "importantAuto": True,
            },
        )

        assert news_data["news_id"] == "67557d0374b91122ef77c7c9"
        assert news_data["is_update"] is True
        assert news_data["applied_updates"] == {"important-auto"}
        assert news_data["is_important"] is True
        assert news_data["time"] == datetime.fromtimestamp(1734042346123 / 1000, timezone.utc)
