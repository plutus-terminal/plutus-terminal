"""Handle new from Synoptic Streams."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Optional

import orjson as json
import re2
from tenacity import (
    before_sleep_log,
    retry,
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


class SynopticNews(NewsFetcher):
    """Handle news from Synoptic Streams."""

    NEWS_SERVICE_NAME = "Synoptic"

    def __init__(self, pass_guard: PasswordGuard) -> None:
        """Initialize shared variables.

        Args:
            pass_guard (PasswordGuard): Password guard
        """
        self._pass_guard = pass_guard
        self.wss = "wss://api.synoptic.com/graphql?format=tree&apiKey={}"
        self._socket: Optional[ClientConnection] = None
        self._compiled_pattern_quote = re2.compile(r"https?://\S+")

    async def websocket_connect(self, api_key: str) -> ClientConnection:
        """Connect to websocket to fetch news.

        Returns:
            ClientConnection: Websocket connection.
            api_key (str): API key
        """
        self._socket = await connect(self.wss.format(api_key), ping_interval=5, ping_timeout=10)
        LOGGER.info("Connected to %s Websocket", self.NEWS_SERVICE_NAME)
        return self._socket

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def _ensure_websocket_connection(self) -> bool:
        """Ensure websocket is connected.

        Returns:
            bool: True if API is available.
        """
        if self._socket is None or self._socket.state == State.CLOSED:
            LOGGER.warning(
                "%s Websocket disconnected. Attempting to reconnect websocket...",
                self.NEWS_SERVICE_NAME,
            )
            try:
                api_key = keyring_manager.get_news_source_api_key(
                    self.NEWS_SERVICE_NAME,
                    pass_guard=self._pass_guard,
                )
            except KeyringPasswordNotFoundError:
                LOGGER.warning("%s API key not found", self.NEWS_SERVICE_NAME)
                return False
            await self.websocket_connect(api_key)
        return True

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
        if not await self._ensure_websocket_connection():
            return

        LOGGER.info("Subscribed to %s news source.", self.NEWS_SERVICE_NAME)
        async for message in self._socket:  # type: ignore
            LOGGER.debug("New raw message received from %s", self.NEWS_SERVICE_NAME)
            json_message = json.loads(message)
            formated_message = self.format_news(json_message)
            message_bus.raw_news.emit(formated_message)

    async def fetch_old_news(self, limit: int) -> list[NewsData]:  # noqa: ARG002
        """Fetch old news from API.

        Only implementing to satisfy protocol.
        """
        return []

    def format_news(self, news_message: dict) -> NewsData:
        """Format given news.

        Args:
            news_message (dict): News message to be formatted.

        Returns:
            NewsData : Formatted news.
        """
        title = self.NEWS_SERVICE_NAME
        link = ""
        body = news_message.get("en", news_message.get("title", ""))
        icon = news_message.get("icon", "")
        source = "SynopticStreams"
        time = datetime.fromtimestamp(news_message["time"] / 1000, timezone.utc)
        coin = {news_message.get("coin", "")} if news_message.get("coin", "") else set()
        suggestions = news_message.get("suggestions", [])
        image = news_message.get("image", "")

        if suggestions:
            for item in suggestions:
                coin.add(item["coin"])

        urls = list(self._compiled_pattern_quote.finditer(body))
        if urls:
            link = str(urls[0].group(0))

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
        if self._socket is not None and self._socket.state not in (State.CLOSED, State.CLOSING):
            await self._socket.close()
