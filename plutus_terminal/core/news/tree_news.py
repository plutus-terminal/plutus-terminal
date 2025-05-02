"""Handle news from Tree Of Alpha."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Optional

from httpx import AsyncClient
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
from plutus_terminal.core.news.base import NewsFetcher
from plutus_terminal.core.types_ import NewsData
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)


class TreeNews(NewsFetcher):
    """News fetcher for Tree Of Alpha News."""

    NEWS_SERVICE_NAME = "TreeOfAlpha"

    def __init__(self, pass_guard: PasswordGuard) -> None:
        """Initialize shared variables.

        Args:
            pass_guard (PasswordGuard): Password guard
        """
        self._pass_guard = pass_guard
        self.wss = "wss://news.treeofalpha.com/ws"
        self._socket: Optional[ClientConnection] = None
        self._compiled_pattern_quote = re2.compile(r"\bQuote\s+\[(@\w+)\]\([^)]*\)")
        self._compiled_pattern_tweet_title = re2.compile(r"\(@([a-zA-Z0-9_]+)\)")

    async def websocket_connect(self) -> ClientConnection:
        """Connect to websocket to fetch news.

        Returns:
            WebSocketClientProtocol: Websocket connection.
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
            tree_api_key = keyring_manager.get_news_source_api_key(
                self.NEWS_SERVICE_NAME,
                pass_guard=self._pass_guard,
            )
        except KeyringPasswordNotFoundError:
            LOGGER.warning("%s API key not found", self.NEWS_SERVICE_NAME)
            return
        if not self._socket:
            return
        login_attempt = await self._socket.recv()
        LOGGER.info("%s login result: %s", self.NEWS_SERVICE_NAME, login_attempt)
        await self._socket.send(f"login {tree_api_key}")

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
            list[NewsData]: List of old news. This list is espected to be ordered
            from latest to oldest.
        """
        request_url = f"https://news.treeofalpha.com/api/news?limit={limit}"
        async with AsyncClient() as client:
            response = await client.get(request_url)
        response.raise_for_status()
        data = response.json()
        list_news = [self.format_news(news) for news in data]
        return list_news[::-1]

    def format_news(self, news_message: dict) -> NewsData:  # noqa: C901, PLR0915
        """Format given news.

        Args:
            news_message (dict): News message to be formated.

        Returns:
            NewsData: Formated news.
        """
        title = news_message.get("en", news_message.get("title", ""))
        link = news_message.get("url", news_message.get("link", ""))
        body = news_message.get("body", "")
        icon = news_message.get("icon", "")
        source = news_message.get("source", news_message.get("type", ""))
        time = datetime.fromtimestamp(news_message["time"] / 1000, timezone.utc)
        coin = {news_message.get("coin", "")} if news_message.get("coin", "") else set()
        suggestions = news_message.get("suggestions", [])
        image = news_message.get("image", "")

        is_quote = False
        quote_message = ""
        quote_user = ""
        quote_image = ""

        is_reply = False
        is_self_reply = False
        reply_message = ""
        reply_user = ""
        reply_image = ""

        is_retweet = False
        retweet_user = ""

        if suggestions:
            for item in suggestions:
                coin.add(item["coin"])

        if not body:
            title_split = title.split(":")
            title = title_split[0].strip()
            body = "".join(title_split[1:]).strip()

        if news_message.get("type") == "direct":
            source = "Twitter"

        if source == "Twitter":
            match = self._compiled_pattern_tweet_title.search(title)
            if match:
                title = f"@{match.group(1)}"
            is_quote = news_message["info"].get("isQuote", False)
            is_reply = news_message["info"].get("isReply", False)
            is_self_reply = news_message["info"].get("isSelfReply", False)
            is_retweet = news_message["info"].get("isRetweet", False)

        if is_quote:
            match = self._compiled_pattern_quote.search(body)
            if match:
                quote_message = body[match.end() :].strip()
                body = body[: match.start()].strip()
                quote_user = str(match.group(1)).strip()
                quote_image = news_message["info"]["quotedUser"].get("image", "")
        elif is_self_reply:
            with contextlib.suppress(KeyError):
                reply_user = f"@{news_message['info']['replyUser']['screen_name']}"
                reply_message = news_message["info"]["replyUser"]["text"]
            with contextlib.suppress(KeyError):
                reply_image = news_message["info"]["quotedUser"]["image"]
        elif is_retweet:
            match = self._compiled_pattern_quote.search(body)
            if match:
                body = body[: match.end()].strip()
                retweet_user = f"@{news_message['info']['quotedUser']['screen_name']}"

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
            feed=self.NEWS_SERVICE_NAME,
            sfx=":/sfx/coin",
            ignored=False,
        )

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        if self._socket is not None and self._socket.state != State.CLOSED:
            await self._socket.close()
