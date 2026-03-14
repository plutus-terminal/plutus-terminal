# ruff: noqa: S101, PT009, PT027, SLF001

"""Lifecycle parity tests for Orderly websocket auth, ack, and reconnect flows."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import json
import unittest
from unittest.mock import AsyncMock, patch

from websockets import State

from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials, OrderlyEndpoints
from plutus_terminal.core.exchange.orderly.websocket import (
    OrderlyWebsocketAuthError,
    OrderlyWebsocketManager,
    OrderlyWebsocketSubscriptionError,
)
from plutus_terminal.core.exchange.orderly.ws_topics import EXECUTION_REPORT_TOPIC


@dataclass
class _FakeSocket:
    recv_messages: deque[bytes] = field(default_factory=deque)
    sent_messages: list[dict[str, object]] = field(default_factory=list)
    state: State = State.OPEN

    async def send(self, payload: str) -> None:
        self.sent_messages.append(json.loads(payload))

    async def recv(self) -> bytes:
        return self.recv_messages.popleft()

    async def close(self) -> None:
        self.state = State.CLOSED


def _build_manager() -> OrderlyWebsocketManager:
    return OrderlyWebsocketManager(
        endpoints=OrderlyEndpoints(
            rest_url="https://example.invalid",
            public_ws_url="wss://public.example.invalid",
            private_ws_url="wss://private.example.invalid",
        ),
        credentials=OrderlyCredentials(
            account_id="account-id",
            orderly_key="key",
            orderly_secret="secret",  # noqa: S106
        ),
    )


def _encode(message: dict[str, object]) -> bytes:
    return json.dumps(message).encode("utf-8")


class OrderlyWebsocketLifecycleParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify websocket lifecycle behavior stays aligned with Orderly expectations."""

    async def test_connect_private_authenticates_before_replaying_saved_subscriptions(self) -> None:
        """Authenticate private sockets before replaying buffered private subscriptions."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket()
        manager._private_topics.add(EXECUTION_REPORT_TOPIC)
        call_order: list[str] = []

        async def record_auth(_: _FakeSocket) -> None:
            call_order.append("auth")

        async def record_subscribe(*args: object, **kwargs: object) -> None:
            del args, kwargs
            call_order.append("subscribe")

        manager._authenticate_private_socket = AsyncMock(side_effect=record_auth)  # type: ignore[method-assign]
        manager._subscribe_many = AsyncMock(side_effect=record_subscribe)  # type: ignore[method-assign]

        with patch(
            "plutus_terminal.core.exchange.orderly.websocket.connect",
            AsyncMock(return_value=socket),
        ) as connect_mock:
            # Act
            connected_socket = await manager.connect_private()

        # Assert
        assert connected_socket is socket
        assert call_order == ["auth", "subscribe"]
        connect_mock.assert_awaited_once_with(
            "wss://private.example.invalid/account-id",
            ping_interval=10,
            ping_timeout=10,
        )

    async def test_connect_private_stops_before_resubscribe_when_authentication_fails(self) -> None:
        """Do not replay private subscriptions if the reconnect auth ack is rejected."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket()
        manager._private_topics.add(EXECUTION_REPORT_TOPIC)
        manager._authenticate_private_socket = AsyncMock(  # type: ignore[method-assign]
            side_effect=OrderlyWebsocketAuthError("auth rejected"),
        )
        manager._subscribe_many = AsyncMock()  # type: ignore[method-assign]

        with patch(
            "plutus_terminal.core.exchange.orderly.websocket.connect",
            AsyncMock(return_value=socket),
        ):
            # Act / Assert
            with self.assertRaisesRegex(OrderlyWebsocketAuthError, "auth rejected"):
                await asyncio.wait_for(manager.connect_private(), timeout=0.5)

        manager._subscribe_many.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_normalize_event_replies_with_pong_to_server_ping_frames(self) -> None:
        """Reply with a pong frame when the server emits an Orderly ping event."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket()

        with patch(
            "plutus_terminal.core.exchange.orderly.websocket.time.time",
            return_value=1_700_000_000.123,
        ):
            # Act
            event = await manager._normalize_event(_encode({"event": "ping"}), socket)

        # Assert
        assert event == {"event": "heartbeat", "data": {"event": "ping"}}
        assert socket.sent_messages == [{"event": "pong", "ts": 1_700_000_000_123}]

    async def test_normalize_event_leaves_non_ping_frames_untouched(self) -> None:
        """Return ordinary websocket payloads unchanged when no heartbeat response is needed."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket()
        payload = {"topic": EXECUTION_REPORT_TOPIC, "data": {"orderId": "1"}}

        # Act
        event = await manager._normalize_event(_encode(payload), socket)

        # Assert
        assert event == payload
        assert socket.sent_messages == []

    async def test_send_request_and_wait_for_ack_accepts_matching_ack_after_other_ids(self) -> None:
        """Match websocket acknowledgements by request id before treating them as success."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket(
            recv_messages=deque(
                [
                    _encode({"id": "subscribe-99", "event": "subscribe", "success": True}),
                    _encode({"id": "subscribe-5", "event": "subscribe", "success": True}),
                ],
            ),
        )
        payload = {"id": "subscribe-5", "event": "subscribe", "topic": EXECUTION_REPORT_TOPIC}

        # Act
        await manager._send_request_and_wait_for_ack(
            socket,
            payload,
            recv_lock=manager._private_recv_lock,
            request_lock=manager._private_request_lock,
            event_buffer=manager._private_buffer,
            error_type=OrderlyWebsocketSubscriptionError,
        )

        # Assert
        assert socket.sent_messages == [payload]
        assert list(manager._private_buffer) == []

    async def test_send_request_and_wait_for_ack_preserves_request_id_in_error_ack_failures(
        self,
    ) -> None:
        """Preserve the websocket request id when Orderly returns an error acknowledgement."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket(
            recv_messages=deque(
                [
                    _encode(
                        {
                            "id": "subscribe-5",
                            "event": "subscribe",
                            "success": False,
                            "errorMsg": "topic rejected",
                        },
                    ),
                ],
            ),
        )
        payload = {"id": "subscribe-5", "event": "subscribe", "topic": EXECUTION_REPORT_TOPIC}

        # Act / Assert
        with self.assertRaisesRegex(
            OrderlyWebsocketSubscriptionError,
            r"subscribe-5.*topic rejected|topic rejected.*subscribe-5",
        ):
            await manager._send_request_and_wait_for_ack(
                socket,
                payload,
                recv_lock=manager._private_recv_lock,
                request_lock=manager._private_request_lock,
                event_buffer=manager._private_buffer,
                error_type=OrderlyWebsocketSubscriptionError,
            )

    async def test_connect_private_reauthenticates_and_resubscribes_after_socket_reset(
        self,
    ) -> None:
        """Reconnect private sockets by restoring auth state before replaying saved topics."""
        # Arrange
        manager = _build_manager()
        first_socket = _FakeSocket()
        second_socket = _FakeSocket()
        manager._private_topics.add(EXECUTION_REPORT_TOPIC)

        with patch(
            "plutus_terminal.core.exchange.orderly.websocket.connect",
            AsyncMock(side_effect=[first_socket, second_socket]),
        ):
            manager._authenticate_private_socket = AsyncMock()  # type: ignore[method-assign]
            manager._subscribe_many = AsyncMock()  # type: ignore[method-assign]

            # Act
            await manager.connect_private()
            await manager._reset_private_socket()
            connected_socket = await manager.connect_private()

        # Assert
        assert connected_socket is second_socket
        assert manager._authenticate_private_socket.await_count == 2  # type: ignore[attr-defined]
        assert manager._subscribe_many.await_count == 2  # type: ignore[attr-defined]

    async def test_reset_private_socket_preserves_saved_topics_for_future_reconnects(self) -> None:
        """Keep saved private subscriptions locally so reconnect logic can replay them later."""
        # Arrange
        manager = _build_manager()
        manager._private_topics.add(EXECUTION_REPORT_TOPIC)
        manager._private_socket = _FakeSocket()
        manager._private_buffer.append({"topic": EXECUTION_REPORT_TOPIC, "data": {"orderId": "1"}})

        # Act
        await manager._reset_private_socket()

        # Assert
        assert manager._private_socket is None
        assert manager._private_topics == {EXECUTION_REPORT_TOPIC}
        assert list(manager._private_buffer) == []
