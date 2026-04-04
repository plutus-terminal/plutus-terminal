"""Handle news from Phoenix News."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING

from httpx import AsyncClient, HTTPStatusError, Response
import orjson as json
import re2
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)
from websockets import ClientConnection, State, connect

from plutus_terminal.core import keyring_manager
from plutus_terminal.core.exceptions import KeyringPasswordNotFoundError
from plutus_terminal.core.news.base import (
    NewsFetcher,
    default_message_key,
    merge_news_update,
)
from plutus_terminal.core.types_ import NewsData
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)


class PhoenixNews(NewsFetcher):
    """News fetcher for Phoenix News."""

    NEWS_SERVICE_NAME = "PhoenixNews"

    def __init__(self, pass_guard: PasswordGuard) -> None:
        """Initialize shared variables.

        Args:
            pass_guard (PasswordGuard): Password guard
        """
        self._pass_guard = pass_guard
        self.wss = "wss://wss.phoenixnews.io/"
        self._socket: ClientConnection | None = None
        self._compiled_pattern_quote = re2.compile(r"&gt;&gt;QUOTE\s+.+?\s*[^\(@]*\((@\w+)\)")
        self._compiled_pattern_reply = re2.compile(r"&gt;&gt;REPLY\s+.+?\s*[^\(@]*\((@\w+)\)")
        self._compiled_pattern_retweet = re2.compile(r"&gt;&gt;RT\s+.+?\s*[^\(@]*\((@\w+)\)")

    async def websocket_connect(self) -> ClientConnection:
        """Connect to websocket to fetch news.

        Returns:
            ClientConnection: Websocket connection.
        """
        self._socket = await connect(self.wss, ping_interval=5, ping_timeout=10)
        LOGGER.info("Connected to %s Websocket", self.NEWS_SERVICE_NAME)
        return self._socket

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def _ensure_websocket_connection(self) -> None:
        """Ensure websocket is connected."""
        if self._socket is None or self._socket.state == State.CLOSED:
            LOGGER.warning(
                "%s Websocket disconnected. Attempting to reconnect websocket...",
                self.NEWS_SERVICE_NAME,
            )
            await self.websocket_connect()
            await self._login()

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        reraise=True,
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def subscribe_to_wss(self, message_bus: MessageBus) -> None:
        """Subscribe to news wss and emit news signal on new entry.

        Args:
            message_bus (plutus_terminal.message_bus.MessageBus): Message bus
                to emit news messages
        """
        await self._ensure_websocket_connection()

        LOGGER.info("Subscribed to %s news source.", self.NEWS_SERVICE_NAME)
        async for message in self._socket:  # type: ignore
            LOGGER.debug("New raw message received from %s", self.NEWS_SERVICE_NAME)
            json_message = json.loads(message)
            formated_message = self.format_news(json_message)
            message_bus.raw_news.emit(formated_message)

    async def _login(self) -> None:
        """Login to news source."""
        LOGGER.info("Logging in to %s...", self.NEWS_SERVICE_NAME)
        try:
            phoenix_api_key = keyring_manager.get_news_source_api_key(
                self.NEWS_SERVICE_NAME,
                pass_guard=self._pass_guard,
            )
        except KeyringPasswordNotFoundError:
            LOGGER.warning("%s API key not found", self.NEWS_SERVICE_NAME)
            return
        if not self._socket:
            return
        await self._socket.send(f"login {phoenix_api_key}")
        try:
            login_attempt = await asyncio.wait_for(self._socket.recv(), timeout=1)
            login_result = dict(json.loads(login_attempt))
            login_result.pop("apiKey", None)
            login_result.pop("address", None)
            LOGGER.info("%s login result: %s", self.NEWS_SERVICE_NAME, login_result)
        except TimeoutError:
            LOGGER.warning("%s login timed out", self.NEWS_SERVICE_NAME)

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=2),
        stop=stop_after_attempt(5),
        reraise=True,
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_old_news(self, limit: int) -> list[NewsData]:
        """Fetch old news from API.

        Args:
            limit (int): Amount of news to fetch.

        Returns:
            list[NewsData]: List of old news. This list is expected to be ordered.
            from latest to oldest.
        """
        request_url, request_headers = self._get_historical_news_request(limit)
        async with AsyncClient() as client:
            response = await self._fetch_historical_news_response(
                client,
                request_url,
                request_headers,
                limit,
            )
        data = response.json()
        list_news = [self.format_news(news) for news in data]
        return list_news[::-1]

    async def _fetch_historical_news_response(
        self,
        client: AsyncClient,
        request_url: str,
        request_headers: dict[str, str],
        limit: int,
    ) -> Response:
        """Fetch historical news, falling back to the public endpoint if needed."""
        try:
            response = await client.get(request_url, headers=request_headers)
            response.raise_for_status()
        except HTTPStatusError as error:
            if not request_headers:
                raise

            fallback_url = self._get_public_historical_news_request(limit)
            LOGGER.warning(
                "%s historical subscriber endpoint failed with status %s. Falling back to public news endpoint.",
                self.NEWS_SERVICE_NAME,
                error.response.status_code,
            )
            response = await client.get(fallback_url, headers={})
            response.raise_for_status()

        return response

    def _get_historical_news_request(self, limit: int) -> tuple[str, dict[str, str]]:
        """Build the Phoenix historical news request URL and headers."""
        request_url = self._get_public_historical_news_request(limit)

        try:
            phoenix_api_key = keyring_manager.get_news_source_api_key(
                self.NEWS_SERVICE_NAME,
                pass_guard=self._pass_guard,
            )
        except KeyringPasswordNotFoundError:
            return request_url, {}

        if not phoenix_api_key:
            return request_url, {}

        return (
            f"https://api.phoenixnews.io/getAllNews?limit={limit}",
            {"x-api-key": phoenix_api_key},
        )

    def _get_public_historical_news_request(self, limit: int) -> str:
        """Build the Phoenix public historical news request URL."""
        return f"https://api.phoenixnews.io/getLastNews?limit={limit}"

    def format_news(self, news_message: dict) -> NewsData:  # noqa: C901, PLR0915
        """Format given news.

        Args:
            news_message (dict): News message to be formatted.

        Returns:
            NewsData : Formatted news.
        """
        message_type = news_message.get("type", "")
        news_id = news_message.get("_id", "")

        try:
            time = datetime.fromtimestamp(news_message["time"] / 1000, timezone.utc)
        except KeyError:
            time = datetime.fromisoformat(news_message["createdAt"])

        if message_type in {"summary-ai", "important-auto"}:
            return NewsData(
                news_id=news_id,
                title="",
                link="",
                body="",
                image="",
                is_quote=False,
                quote_message="",
                quote_user="",
                quote_image="",
                is_reply=False,
                is_self_reply=False,
                reply_user="",
                reply_message="",
                reply_image="",
                is_retweet=False,
                retweet_user="",
                icon="",
                source="",
                time=time,
                coin=set(),
                feed=self.NEWS_SERVICE_NAME,
                sfx=":/sfx/coin",
                is_update=True,
                update_type=message_type,
                applied_updates={message_type},
                summary_title=news_message.get("summaryAI", ""),
                summary_body=news_message.get("cryptoAI", ""),
                is_important=news_message.get("importantAuto", False),
                ignored=False,
            )

        source = news_message.get("source", "")
        image = news_message.get("image", "")

        is_quote = news_message.get("isQuote", False)
        quote_message = ""
        quote_user = ""
        quote_image = news_message.get("imageQuote", "")

        is_reply = news_message.get("isReply", False)
        is_self_reply = news_message.get("isSelfReply", False)
        reply_message = ""
        reply_user = ""
        reply_image = ""

        is_retweet = news_message.get("isRetweet", False)
        retweet_user = ""

        if source == "Twitter":
            title = f"@{news_message.get('username')}"
            body = news_message.get("body", "")

            if is_quote:
                match = self._compiled_pattern_quote.search(body)
                if match:
                    quote_message = body[match.end() :].strip()
                    body = body[: match.start()].strip()
                    quote_user = str(match.group(1)).strip()
            elif is_reply:
                match = self._compiled_pattern_reply.search(body)
                if match:
                    body = body[match.end() :].strip()
                    reply_user = str(match.group(1)).strip()
            elif is_self_reply:
                match = self._compiled_pattern_reply.search(body)
                if match:
                    body = body[match.end() :].strip()
                    reply_user = title
            elif is_retweet:
                match = self._compiled_pattern_retweet.search(body)
                if match:
                    body = body[match.end() :].strip()
                    retweet_user = str(match.group(1)).strip()
        else:
            title = news_message.get("sourceName", "")
            body = news_message.get("title", "")

        link = news_message.get("url", "")
        icon = news_message.get("icon", "")

        coin = {news_message.get("coin", "")} if news_message.get("coin", "") else set()

        return NewsData(
            news_id=news_id,
            title=title,
            link=link,
            body=body,
            image=image,
            is_quote=is_quote,
            quote_message=quote_message,
            quote_user=quote_user,
            quote_image=quote_image,
            is_reply=is_reply,
            is_self_reply=is_self_reply,
            reply_user=reply_user,
            reply_message=reply_message,
            reply_image=reply_image,
            is_retweet=is_retweet,
            retweet_user=retweet_user,
            icon=icon,
            source=source,
            time=time,
            coin=coin,
            feed=self.NEWS_SERVICE_NAME,
            sfx=":/sfx/coin",
            is_update=False,
            update_type=message_type,
            applied_updates=set(),
            summary_title=news_message.get("summaryAI", ""),
            summary_body=news_message.get("cryptoAI", ""),
            is_important=news_message.get("importantAuto", False),
            ignored=False,
        )

    def get_message_key(self, news_data: NewsData) -> str:
        """Return the stable key for a news message."""
        return default_message_key(news_data)

    def merge_update(self, current_news: NewsData, incoming_news: NewsData) -> NewsData:
        """Merge a partial Phoenix update packet into a full news payload."""
        return merge_news_update(current_news, incoming_news)

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        if self._socket is not None and self._socket.state not in (State.CLOSED, State.CLOSING):
            await self._socket.close()
