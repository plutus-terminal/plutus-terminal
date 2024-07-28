"""Handle news from Tree Of Alpha."""

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

TREE_KEY_NAME = "TreeOfAlpha"


class TreeNews(NewsFetcher):
    """News fetcher for Tree Of Alpha News."""

    def __init__(self) -> None:
        """Initialize shared variables."""
        self.wss = "wss://news.treeofalpha.com/ws"
        self._socket: Optional[WebSocketClientProtocol] = None  # type: ignore
        self._compiled_pattern = re2.compile(r"\bQuote\s+\[(@\w+)\]\([^)]*\)")

    async def websocket_connect(self) -> WebSocketClientProtocol:
        """Connect to websocket to fetch prices.

        Returns:
            WebSocketClientProtocol: Websocket connection.
        """
        if self._socket is None or self._socket.closed:
            self._socket = await connect(self.wss, ping_interval=5, ping_timeout=10)
            LOGGER.info("Connected to TreeOfAlpha Websocket")
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
                "TreeOfAlpha Websocket disconnected. Attempting to reconnect websocket...",
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

        LOGGER.info("Subscribed to TreeOfAlpha news source.")
        async for message in self._socket:  # type: ignore
            LOGGER.debug("New raw message received from TreeOfAlpha")
            json_message = json.loads(message)
            formated_message = self.format_news(json_message)
            message_bus.raw_news_signal.emit(formated_message)

    async def login(self) -> None:
        """Login to news source."""
        LOGGER.info("Logging in to TreeOfAlpha...")
        tree_api_key = keyring.get_password(
            "plutus-terminal:news-source",
            TREE_KEY_NAME,
        )
        if not tree_api_key:
            LOGGER.warning("TreeOfAlph API key not found")
            return
        await self._ensure_websocket_connection()
        if not self._socket:
            return
        await self._socket.send(f"login {tree_api_key}")
        login_attempt = await self._socket.recv()
        login_attempt = json.loads(login_attempt)
        login_attempt.setdefault("user", {})
        login_attempt["user"].pop("address", None)
        LOGGER.info("TreeOfAlpha login result: %s", login_attempt)

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

    def format_news(self, news_message: dict) -> NewsData:
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
        quote = ""
        quoter = ""
        quote_image = ""

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
            is_quote = news_message["info"]["isQuote"]

        if is_quote:
            match = self._compiled_pattern.search(body)
            if match:
                quote = body[match.end() :].strip()
                body = body[: match.start()].strip()
                quoter = str(match.group(1)).strip()

        return NewsData(
            title=title,
            link=link,
            body=body,
            image=image,
            is_quote=is_quote,
            quote=quote,
            quoter=quoter,
            quote_image=quote_image,
            icon=icon,
            source=source,
            time=time,
            coin=coin,
            feed="Tree Of Alpha",
            sfx=":/sfx/coin",
            ignored=False,
        )

    async def stop_async(self) -> None:
        """Stop infinite loops and close connections."""
        if self._socket is not None:
            await self._socket.close()
