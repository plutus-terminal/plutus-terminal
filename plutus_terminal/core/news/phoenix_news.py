"""Handle news from Phoenix News."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Optional

from httpx import AsyncClient
import keyring
import orjson as json
import re2
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)
from websockets.client import WebSocketClientProtocol, connect

from plutus_terminal.core.news.base import NewsFetcher
from plutus_terminal.core.types_ import NewsData
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.core.news.base import NewsMessageBus

LOGGER = logging.getLogger(__name__)

PHOENIX_KEY_NAME = "PhoenixNews"


class PhoenixNews(NewsFetcher):
    """News fetcher for Phoenix News."""

    def __init__(self) -> None:
        """Initialize shared variables."""
        self.wss = "wss://wss.phoenixnews.io/"
        self._socket: Optional[WebSocketClientProtocol] = None  # type: ignore
        self._compiled_pattern_quote = re2.compile(r"&gt;&gt;QUOTE\s+.+?\s*[^\(@]*\((@\w+)\)")
        self._compiled_pattern_reply = re2.compile(r"&gt;&gt;REPLY\s+.+?\s*[^\(@]*\((@\w+)\)")
        self._compiled_pattern_retweet = re2.compile(r"&gt;&gt;RT\s+.+?\s*[^\(@]*\((@\w+)\)")

    async def websocket_connect(self) -> WebSocketClientProtocol:
        """Connect to websocket to fetch prices.

        Returns:
            WebSocketClientProtocol: Websocket connection.
        """
        if self._socket is None or self._socket.closed:
            self._socket = await connect(self.wss, ping_interval=5, ping_timeout=10)
            LOGGER.info("Connected to PhoenixNews Websocket")
        return self._socket

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def _ensure_websocket_connection(self) -> None:
        """Ensure websocket is connected."""
        if self._socket is None or self._socket.closed:
            LOGGER.warning(
                "PhoenixNews Websocket disconnected. Attempting to reconnect websocket...",
            )
            await self.websocket_connect()

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        reraise=True,
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def subscribe_to_wss(self, message_bus: NewsMessageBus) -> None:
        """Subscribe to news wss and emit news signal on new entry.

        Args:
            message_bus (plutus_terminal.ui.thread.NewsMessageBus): Message bus
                to emit news messages
        """
        await self._ensure_websocket_connection()

        LOGGER.info("Subscribed to PhoenixNews news source.")
        async for message in self._socket:  # type: ignore
            LOGGER.debug("New raw message received from PhonixNews")
            json_message = json.loads(message)
            formated_message = self.format_news(json_message)
            message_bus.raw_news_signal.emit(formated_message)

    async def login(self) -> None:
        """Login to news source."""
        LOGGER.info("Logging in to PhoenixNews...")
        phoenix_api_key = keyring.get_password(
            "plutus-terminal:news-source",
            PHOENIX_KEY_NAME,
        )
        if not phoenix_api_key:
            LOGGER.warning("PhoenixNews API key not found")
            return
        await self._ensure_websocket_connection()
        if not self._socket:
            return
        await self._socket.send(f"login {phoenix_api_key}")
        login_attempt = await self._socket.recv()
        login_attempt = json.loads(login_attempt)
        login_attempt.pop("apiKey", None)
        login_attempt.pop("address", None)
        LOGGER.info("PhoenixNews login result: %s", login_attempt)

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
        request_url = f"https://api.phoenixnews.io/getLastNews?limit={limit}"
        async with AsyncClient() as client:
            response = await client.get(request_url)
        response.raise_for_status()
        data = response.json()
        list_news = [self.format_news(news) for news in data]
        return list_news[::-1]

    def format_news(self, news_message: dict) -> NewsData:  # noqa: C901
        """Format given news.

        Args:
            news_message (dict): News message to be formatted.

        Returns:
            NewsData : Formatted news.
        """
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
            title = f'@{news_message.get("username")}'
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

        try:
            time = datetime.fromtimestamp(news_message["time"] / 1000, timezone.utc)
        except KeyError:
            time = datetime.fromisoformat(
                news_message["createdAt"].replace("Z", "+00:00"),
            )

        coin = {news_message.get("coin", "")} if news_message.get("coin", "") else set()

        return NewsData(
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
            feed="Phoenix News",
            sfx=":/sfx/coin",
            ignored=False,
        )

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        if self._socket is not None:
            await self._socket.close()
