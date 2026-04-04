# ruff: noqa: S101
"""Tests for Phoenix same-ID update payload parsing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Self
from unittest.mock import patch

from httpx import HTTPStatusError, Request, Response

from plutus_terminal.core.exceptions import KeyringPasswordNotFoundError
from plutus_terminal.core.news.phoenix_news import PhoenixNews


class TestPhoenixNewsUpdates:
    """Tests for Phoenix update message parsing."""

    def test_fetch_old_news_uses_get_all_news_when_api_key_exists(self) -> None:
        """Historical Phoenix fetches should use the subscriber endpoint with the API key."""
        phoenix_news = PhoenixNews(object())
        captured_requests: list[tuple[str, dict[str, str]]] = []

        class _ResponseStub:
            def raise_for_status(self) -> None:
                """Pretend the HTTP response succeeded."""

            def json(self) -> list[dict[str, object]]:
                """Return an empty news payload."""
                return []

        class _AsyncClientStub:
            async def __aenter__(self) -> Self:
                """Enter the async client context."""
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                """Exit the async client context."""

            async def get(self, url: str, headers: dict[str, str]) -> _ResponseStub:
                """Capture the request and return a stub response."""
                captured_requests.append((url, headers))
                return _ResponseStub()

        with (
            patch(
                "plutus_terminal.core.news.phoenix_news.keyring_manager.get_news_source_api_key",
                return_value="phoenix-api-key",
            ),
            patch(
                "plutus_terminal.core.news.phoenix_news.AsyncClient",
                return_value=_AsyncClientStub(),
            ),
        ):
            assert asyncio.run(phoenix_news.fetch_old_news(50)) == []

        assert captured_requests == [
            (
                "https://api.phoenixnews.io/getAllNews?limit=50",
                {"x-api-key": "phoenix-api-key"},
            ),
        ]

    def test_fetch_old_news_uses_public_endpoint_without_api_key(self) -> None:
        """Historical Phoenix fetches should keep using the public endpoint without a key."""
        phoenix_news = PhoenixNews(object())
        captured_requests: list[tuple[str, dict[str, str]]] = []

        class _ResponseStub:
            def raise_for_status(self) -> None:
                """Pretend the HTTP response succeeded."""

            def json(self) -> list[dict[str, object]]:
                """Return an empty news payload."""
                return []

        class _AsyncClientStub:
            async def __aenter__(self) -> Self:
                """Enter the async client context."""
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                """Exit the async client context."""

            async def get(self, url: str, headers: dict[str, str]) -> _ResponseStub:
                """Capture the request and return a stub response."""
                captured_requests.append((url, headers))
                return _ResponseStub()

        with (
            patch(
                "plutus_terminal.core.news.phoenix_news.keyring_manager.get_news_source_api_key",
                side_effect=KeyringPasswordNotFoundError("missing"),
            ),
            patch(
                "plutus_terminal.core.news.phoenix_news.AsyncClient",
                return_value=_AsyncClientStub(),
            ),
        ):
            assert asyncio.run(phoenix_news.fetch_old_news(25)) == []

        assert captured_requests == [("https://api.phoenixnews.io/getLastNews?limit=25", {})]

    def test_fetch_old_news_falls_back_to_public_endpoint_when_subscriber_request_fails(
        self,
    ) -> None:
        """Historical Phoenix fetches should fall back to the public endpoint on subscriber errors."""
        phoenix_news = PhoenixNews(object())
        captured_requests: list[tuple[str, dict[str, str]]] = []

        class _ErrorResponseStub:
            def __init__(self, url: str) -> None:
                """Store the failing URL."""
                self._url = url

            def raise_for_status(self) -> None:
                """Raise a client error for the subscriber endpoint."""
                message = "Client error '400 Bad Request'"
                request = Request("GET", self._url)
                raise HTTPStatusError(
                    message,
                    request=request,
                    response=Response(400, request=request),
                )

        class _SuccessResponseStub:
            def raise_for_status(self) -> None:
                """Pretend the fallback HTTP response succeeded."""

            def json(self) -> list[dict[str, object]]:
                """Return an empty news payload."""
                return []

        class _AsyncClientStub:
            async def __aenter__(self) -> Self:
                """Enter the async client context."""
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                """Exit the async client context."""

            async def get(
                self, url: str, headers: dict[str, str]
            ) -> _ErrorResponseStub | _SuccessResponseStub:
                """Fail on subscriber endpoint and succeed on public fallback."""
                captured_requests.append((url, headers))
                if "getAllNews" in url:
                    return _ErrorResponseStub(url)
                return _SuccessResponseStub()

        with (
            patch(
                "plutus_terminal.core.news.phoenix_news.keyring_manager.get_news_source_api_key",
                return_value="phoenix-api-key",
            ),
            patch(
                "plutus_terminal.core.news.phoenix_news.AsyncClient",
                return_value=_AsyncClientStub(),
            ),
        ):
            assert asyncio.run(phoenix_news.fetch_old_news(25)) == []

        assert captured_requests == [
            (
                "https://api.phoenixnews.io/getAllNews?limit=25",
                {"x-api-key": "phoenix-api-key"},
            ),
            ("https://api.phoenixnews.io/getLastNews?limit=25", {}),
        ]

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
