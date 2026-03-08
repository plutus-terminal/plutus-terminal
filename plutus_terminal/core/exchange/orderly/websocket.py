"""Websocket manager for Orderly public and private streams."""

from __future__ import annotations

import asyncio
from collections import deque
from itertools import count
import logging
import time
from typing import TYPE_CHECKING, Any

import orjson
from tenacity import before_sleep_log, retry, wait_exponential
from websockets import ClientConnection, State, connect
from websockets.exceptions import ConnectionClosed

from plutus_terminal.core.exchange.orderly.auth import build_ws_auth_message
from plutus_terminal.core.exchange.orderly.ws_topics import (
    ACKABLE_WS_EVENTS,
    build_topic_command_message,
)
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials, OrderlyEndpoints

LOGGER = logging.getLogger(__name__)
_ACK_TIMEOUT_SECONDS = 5.0


class OrderlyWebsocketError(Exception):
    """Base websocket protocol error for Orderly streams."""


class OrderlyWebsocketAuthError(OrderlyWebsocketError):
    """Raised when private websocket authentication fails."""


class OrderlyWebsocketSubscriptionError(OrderlyWebsocketError):
    """Raised when websocket subscribe or unsubscribe fails."""


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
        self._public_request_lock = asyncio.Lock()
        self._private_request_lock = asyncio.Lock()
        self._public_buffer: deque[dict[str, Any]] = deque()
        self._private_buffer: deque[dict[str, Any]] = deque()
        self._request_ids = count(1)

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def connect_public(self) -> ClientConnection:
        """Connect to public websocket endpoint."""
        if self._public_socket is None or self._public_socket.state != State.OPEN:
            if self._public_socket is not None and self._public_socket.state != State.CLOSED:
                await self._public_socket.close()
            url = f"{self._endpoints.public_ws_url}/{self._credentials.account_id}"
            self._public_socket = await connect(url, ping_interval=10, ping_timeout=10)
            LOGGER.info("Connected to Orderly public websocket")
            if self._public_topics:
                await self._subscribe_many(
                    self._public_socket,
                    self._public_topics,
                    recv_lock=self._public_recv_lock,
                    request_lock=self._public_request_lock,
                    event_buffer=self._public_buffer,
                )
        return self._public_socket

    @retry(
        wait=wait_exponential(multiplier=1, min=0.4, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def connect_private(self) -> ClientConnection:
        """Connect to private websocket endpoint and authenticate."""
        if self._private_socket is None or self._private_socket.state != State.OPEN:
            if self._private_socket is not None and self._private_socket.state != State.CLOSED:
                await self._private_socket.close()
            url = f"{self._endpoints.private_ws_url}/{self._credentials.account_id}"
            self._private_socket = await connect(url, ping_interval=10, ping_timeout=10)
            LOGGER.info("Connected to Orderly private websocket")
            await self._authenticate_private_socket(self._private_socket)
            if self._private_topics:
                await self._subscribe_many(
                    self._private_socket,
                    self._private_topics,
                    recv_lock=self._private_recv_lock,
                    request_lock=self._private_request_lock,
                    event_buffer=self._private_buffer,
                )
        return self._private_socket

    async def subscribe_public(self, topics: Iterable[str]) -> None:
        """Subscribe to public topics and keep them for reconnects."""
        normalized_topics = tuple(topics)
        try:
            socket = await self.connect_public()
            await self._subscribe_many(
                socket,
                normalized_topics,
                recv_lock=self._public_recv_lock,
                request_lock=self._public_request_lock,
                event_buffer=self._public_buffer,
            )
        except OrderlyWebsocketSubscriptionError as error:
            if not _is_closed_before_ack_error(error):
                raise
            LOGGER.warning(
                "Public websocket closed during subscribe; reconnecting once for topics=%s",
                normalized_topics,
            )
            await self._reset_public_socket()
            socket = await self.connect_public()
            await self._subscribe_many(
                socket,
                normalized_topics,
                recv_lock=self._public_recv_lock,
                request_lock=self._public_request_lock,
                event_buffer=self._public_buffer,
            )
        self._public_topics.update(normalized_topics)

    async def subscribe_private(self, topics: Iterable[str]) -> None:
        """Subscribe to private topics and keep them for reconnects."""
        normalized_topics = tuple(topics)
        try:
            socket = await self.connect_private()
            await self._subscribe_many(
                socket,
                normalized_topics,
                recv_lock=self._private_recv_lock,
                request_lock=self._private_request_lock,
                event_buffer=self._private_buffer,
            )
        except OrderlyWebsocketSubscriptionError as error:
            if not _is_closed_before_ack_error(error):
                raise
            LOGGER.warning(
                "Private websocket closed during subscribe; reconnecting once for topics=%s",
                normalized_topics,
            )
            await self._reset_private_socket()
            socket = await self.connect_private()
            await self._subscribe_many(
                socket,
                normalized_topics,
                recv_lock=self._private_recv_lock,
                request_lock=self._private_request_lock,
                event_buffer=self._private_buffer,
            )
        self._private_topics.update(normalized_topics)

    async def unsubscribe_public(self, topics: Iterable[str]) -> None:
        """Unsubscribe from public topics."""
        normalized_topics = tuple(topics)
        try:
            socket = await self.connect_public()
            await self._unsubscribe_many(
                socket,
                normalized_topics,
                recv_lock=self._public_recv_lock,
                request_lock=self._public_request_lock,
                event_buffer=self._public_buffer,
            )
        except OrderlyWebsocketSubscriptionError as error:
            if not _is_closed_before_ack_error(error):
                raise
            LOGGER.warning(
                "Public websocket closed during unsubscribe; dropping local topics=%s",
                normalized_topics,
            )
            await self._reset_public_socket()
        for topic in normalized_topics:
            self._public_topics.discard(topic)

    async def unsubscribe_private(self, topics: Iterable[str]) -> None:
        """Unsubscribe from private topics."""
        normalized_topics = tuple(topics)
        try:
            socket = await self.connect_private()
            await self._unsubscribe_many(
                socket,
                normalized_topics,
                recv_lock=self._private_recv_lock,
                request_lock=self._private_request_lock,
                event_buffer=self._private_buffer,
            )
        except OrderlyWebsocketSubscriptionError as error:
            if not _is_closed_before_ack_error(error):
                raise
            LOGGER.warning(
                "Private websocket closed during unsubscribe; dropping local topics=%s",
                normalized_topics,
            )
            await self._reset_private_socket()
        for topic in normalized_topics:
            self._private_topics.discard(topic)

    async def next_public_event(self) -> dict[str, Any]:
        """Read and decode one public websocket message."""
        return await self._next_event(
            connect_socket=self.connect_public,
            recv_lock=self._public_recv_lock,
            event_buffer=self._public_buffer,
        )

    async def next_private_event(self) -> dict[str, Any]:
        """Read and decode one private websocket message."""
        return await self._next_event(
            connect_socket=self.connect_private,
            recv_lock=self._private_recv_lock,
            event_buffer=self._private_buffer,
        )

    async def stop(self) -> None:
        """Close sockets and stop processing loops."""
        self._stop_event.set()
        await self._reset_public_socket()
        await self._reset_private_socket()

    def should_stop(self) -> bool:
        """Return whether stop was requested."""
        return self._stop_event.is_set()

    def has_public_topics(self) -> bool:
        """Return whether any public topics are currently subscribed."""
        return bool(self._public_topics)

    async def ensure_connections(self) -> None:
        """Ensure both websockets are connected and authenticated."""
        await self.connect_public()
        await self.connect_private()

    async def _authenticate_private_socket(self, socket: ClientConnection) -> None:
        """Authenticate private socket using Orderly auth event."""
        auth_message = build_ws_auth_message(
            self._credentials,
            request_id=self._next_request_id("auth"),
            timestamp_ms=int(time.time() * 1000),
        )
        try:
            await self._send_request_and_wait_for_ack(
                socket,
                auth_message,
                recv_lock=self._private_recv_lock,
                request_lock=self._private_request_lock,
                event_buffer=self._private_buffer,
                error_type=OrderlyWebsocketAuthError,
            )
        except ConnectionClosed as error:
            msg = "Orderly private websocket closed before auth acknowledgement."
            raise OrderlyWebsocketAuthError(msg) from error

    async def _subscribe_many(
        self,
        socket: ClientConnection,
        topics: Iterable[str],
        *,
        recv_lock: asyncio.Lock,
        request_lock: asyncio.Lock,
        event_buffer: deque[dict[str, Any]],
    ) -> None:
        """Send subscribe payloads for all provided topics."""
        for topic in topics:
            payload = build_topic_command_message(
                self._next_request_id("subscribe"),
                "subscribe",
                topic,
            )
            await self._send_request_and_wait_for_ack(
                socket,
                payload,
                recv_lock=recv_lock,
                request_lock=request_lock,
                event_buffer=event_buffer,
                error_type=OrderlyWebsocketSubscriptionError,
            )

    async def _unsubscribe_many(
        self,
        socket: ClientConnection,
        topics: Iterable[str],
        *,
        recv_lock: asyncio.Lock,
        request_lock: asyncio.Lock,
        event_buffer: deque[dict[str, Any]],
    ) -> None:
        """Send unsubscribe payloads for all provided topics."""
        for topic in topics:
            payload = build_topic_command_message(
                self._next_request_id("unsubscribe"),
                "unsubscribe",
                topic,
            )
            await self._send_request_and_wait_for_ack(
                socket,
                payload,
                recv_lock=recv_lock,
                request_lock=request_lock,
                event_buffer=event_buffer,
                error_type=OrderlyWebsocketSubscriptionError,
            )

    async def _next_event(
        self,
        *,
        connect_socket: Callable[[], Awaitable[ClientConnection]],
        recv_lock: asyncio.Lock,
        event_buffer: deque[dict[str, Any]],
    ) -> dict[str, Any]:
        """Read next non-ack event, prioritizing buffered push messages."""
        if event_buffer:
            return event_buffer.popleft()

        socket = await connect_socket()

        async with recv_lock:
            if event_buffer:
                return event_buffer.popleft()
            while True:
                raw_message = await socket.recv()
                event = await self._normalize_event(raw_message, socket)
                if _is_ack_event(event):
                    _log_unsolicited_ack(event)
                    continue
                if event.get("event") == "heartbeat":
                    continue
                return event

    async def _send_request_and_wait_for_ack(
        self,
        socket: ClientConnection,
        payload: dict[str, Any],
        *,
        recv_lock: asyncio.Lock,
        request_lock: asyncio.Lock,
        event_buffer: deque[dict[str, Any]],
        error_type: type[OrderlyWebsocketError],
    ) -> None:
        """Send command and wait for matching acknowledgement while buffering push events."""
        request_id = str(payload.get("id", ""))
        expected_event = str(payload.get("event", ""))

        async with request_lock, recv_lock:
            try:
                await socket.send(orjson.dumps(payload).decode("utf-8"))
                async with asyncio.timeout(_ACK_TIMEOUT_SECONDS):
                    while True:
                        raw_message = await socket.recv()
                        event = await self._normalize_event(raw_message, socket)
                        if _matches_ack(
                            event, request_id=request_id, expected_event=expected_event
                        ):
                            _validate_ack(event, error_type)
                            return
                        if _is_ack_event(event):
                            _log_unsolicited_ack(event)
                            continue
                        if event.get("event") == "heartbeat":
                            continue
                        event_buffer.append(event)
            except ConnectionClosed as error:
                msg = (
                    "Orderly websocket closed before acknowledgement "
                    f"for {expected_event}:{request_id}."
                )
                raise error_type(msg) from error
            except TimeoutError as error:
                msg = (
                    "Timed out waiting for Orderly websocket acknowledgement "
                    f"for {expected_event}:{request_id}."
                )
                raise error_type(msg) from error

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

    def _next_request_id(self, prefix: str) -> str:
        """Build unique request identifier for ws auth/subscription commands."""
        return f"{prefix}-{next(self._request_ids)}"

    async def _reset_public_socket(self) -> None:
        """Close and discard the public socket after a disconnect race."""
        if self._public_socket is not None and self._public_socket.state != State.CLOSED:
            await self._public_socket.close()
        self._public_socket = None
        self._public_buffer.clear()

    async def _reset_private_socket(self) -> None:
        """Close and discard the private socket after a disconnect race."""
        if self._private_socket is not None and self._private_socket.state != State.CLOSED:
            await self._private_socket.close()
        self._private_socket = None
        self._private_buffer.clear()


def _is_ack_event(event: dict[str, Any]) -> bool:
    """Return whether event is an acknowledgement frame for a client command."""
    event_name = event.get("event")
    return isinstance(event_name, str) and event_name in ACKABLE_WS_EVENTS and "id" in event


def _matches_ack(event: dict[str, Any], *, request_id: str, expected_event: str) -> bool:
    """Return whether an acknowledgement matches the request being awaited."""
    return event.get("id") == request_id and event.get("event") == expected_event


def _validate_ack(
    event: dict[str, Any],
    error_type: type[OrderlyWebsocketError],
) -> None:
    """Validate Orderly acknowledgement payload and raise on failure."""
    success = event.get("success")
    if success is True:
        return
    if success is False:
        error_message = str(event.get("errorMsg", "Orderly websocket request failed."))
        raise error_type(error_message)
    msg = "Orderly websocket acknowledgement missing success flag."
    raise error_type(msg)


def _log_unsolicited_ack(event: dict[str, Any]) -> None:
    """Log unexpected acknowledgements without leaking them to stream consumers."""
    log_level = logging.WARNING if event.get("success") is False else logging.DEBUG
    LOGGER.log(
        log_level,
        "Ignoring unsolicited Orderly websocket ack: event=%s id=%s success=%s",
        event.get("event"),
        event.get("id"),
        event.get("success"),
    )


def _is_closed_before_ack_error(error: OrderlyWebsocketSubscriptionError) -> bool:
    """Return whether a subscription error was caused by a closed socket race."""
    return "closed before acknowledgement" in str(error)
