"""Websocket manager for Orderly public and private streams."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import orjson
from tenacity import before_sleep_log, retry, wait_exponential
from websockets import ClientConnection, State, connect

from plutus_terminal.core.exchange.orderly.auth import build_ws_auth_payload
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials, OrderlyEndpoints

LOGGER = logging.getLogger(__name__)


class OrderlyWebsocketManager:
    """Manage resilient Orderly websocket streams and subscriptions."""

    def __init__(
        self,
        endpoints: OrderlyEndpoints,
        credentials: OrderlyCredentials,
    ) -> None:
        """Initialize manager with endpoint URLs and credentials."""
        self._endpoints = endpoints
        self._credentials = credentials
        self._public_socket: ClientConnection | None = None
        self._private_socket: ClientConnection | None = None
        self._public_topics: set[str] = set()
        self._private_topics: set[str] = set()
        self._stop_event = asyncio.Event()
        self._public_recv_lock = asyncio.Lock()
        self._private_recv_lock = asyncio.Lock()

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def connect_public(self) -> ClientConnection:
        """Connect to public websocket endpoint."""
        if self._public_socket is None or self._public_socket.state == State.CLOSED:
            url = f"{self._endpoints.public_ws_url}/{self._credentials.account_id}"
            self._public_socket = await connect(url, ping_interval=10, ping_timeout=10)
            LOGGER.info("Connected to Orderly public websocket")
            if self._public_topics:
                await self._subscribe_many(self._public_socket, self._public_topics)
        return self._public_socket

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def connect_private(self) -> ClientConnection:
        """Connect to private websocket endpoint and authenticate."""
        if self._private_socket is None or self._private_socket.state == State.CLOSED:
            url = f"{self._endpoints.private_ws_url}/{self._credentials.account_id}"
            self._private_socket = await connect(url, ping_interval=10, ping_timeout=10)
            LOGGER.info("Connected to Orderly private websocket")
            await self._authenticate_private_socket(self._private_socket)
            if self._private_topics:
                await self._subscribe_many(self._private_socket, self._private_topics)
        return self._private_socket

    async def subscribe_public(self, topics: Iterable[str]) -> None:
        """Subscribe to public topics and keep them for reconnects."""
        self._public_topics.update(topics)
        socket = await self.connect_public()
        await self._subscribe_many(socket, topics)

    async def subscribe_private(self, topics: Iterable[str]) -> None:
        """Subscribe to private topics and keep them for reconnects."""
        self._private_topics.update(topics)
        socket = await self.connect_private()
        await self._subscribe_many(socket, topics)

    async def unsubscribe_public(self, topics: Iterable[str]) -> None:
        """Unsubscribe from public topics."""
        for topic in topics:
            self._public_topics.discard(topic)
        socket = await self.connect_public()
        await self._unsubscribe_many(socket, topics)

    async def unsubscribe_private(self, topics: Iterable[str]) -> None:
        """Unsubscribe from private topics."""
        for topic in topics:
            self._private_topics.discard(topic)
        socket = await self.connect_private()
        await self._unsubscribe_many(socket, topics)

    async def next_public_event(self) -> dict[str, Any]:
        """Read and decode one public websocket message."""
        async with self._public_recv_lock:
            socket = await self.connect_public()
            raw_message = await socket.recv()
        return await self._normalize_event(raw_message, socket)

    async def next_private_event(self) -> dict[str, Any]:
        """Read and decode one private websocket message."""
        async with self._private_recv_lock:
            socket = await self.connect_private()
            raw_message = await socket.recv()
        return await self._normalize_event(raw_message, socket)

    async def stop(self) -> None:
        """Close sockets and stop processing loops."""
        self._stop_event.set()
        if self._public_socket is not None and self._public_socket.state != State.CLOSED:
            await self._public_socket.close()
        if self._private_socket is not None and self._private_socket.state != State.CLOSED:
            await self._private_socket.close()

    def should_stop(self) -> bool:
        """Return whether stop was requested."""
        return self._stop_event.is_set()

    async def ensure_connections(self) -> None:
        """Ensure both websockets are connected and authenticated."""
        await self.connect_public()
        await self.connect_private()

    async def _authenticate_private_socket(self, socket: ClientConnection) -> None:
        """Authenticate private socket using Orderly auth event."""
        auth_payload = build_ws_auth_payload(self._credentials, timestamp_ms=int(time.time() * 1000))
        auth_message = {
            "id": str(auth_payload["timestamp"]),
            "event": "auth",
            "params": auth_payload,
        }
        await socket.send(orjson.dumps(auth_message).decode("utf-8"))

    async def _subscribe_many(self, socket: ClientConnection, topics: Iterable[str]) -> None:
        """Send subscribe payloads for all provided topics."""
        for topic in topics:
            payload = {"id": f"sub-{topic}", "event": "subscribe", "topic": topic}
            await socket.send(orjson.dumps(payload).decode("utf-8"))

    async def _unsubscribe_many(self, socket: ClientConnection, topics: Iterable[str]) -> None:
        """Send unsubscribe payloads for all provided topics."""
        for topic in topics:
            payload = {"id": f"unsub-{topic}", "event": "unsubscribe", "topic": topic}
            await socket.send(orjson.dumps(payload).decode("utf-8"))

    async def _normalize_event(
        self,
        raw_message: str | bytes,
        socket: ClientConnection,
    ) -> dict[str, Any]:
        """Normalize message and handle ping/pong heartbeat events."""
        event = orjson.loads(raw_message)
        if not isinstance(event, dict):
            return {"event": "unknown", "data": event}

        if event.get("event") == "ping":
            pong_payload = {"event": "pong", "ts": int(time.time() * 1000)}
            await socket.send(orjson.dumps(pong_payload).decode("utf-8"))
            return {"event": "heartbeat", "data": event}

        return event
