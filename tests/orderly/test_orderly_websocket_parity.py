# ruff: noqa: S101, PT009, PT027, SLF001

"""Focused parity tests for Orderly websocket ack handling."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
import unittest
from unittest.mock import AsyncMock

from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials, OrderlyEndpoints
from plutus_terminal.core.exchange.orderly.websocket import (
    OrderlyWebsocketManager,
    OrderlyWebsocketSubscriptionError,
)
from plutus_terminal.core.exchange.orderly.ws_topics import (
    ACCOUNT_TOPICS,
    ALGO_EXECUTION_REPORT_TOPIC,
    build_topic_command_message,
)


@dataclass
class _FakeSocket:
    recv_messages: deque[bytes]
    sent_messages: list[dict[str, object]] = field(default_factory=list)

    async def send(self, payload: str) -> None:
        self.sent_messages.append(json.loads(payload))

    async def recv(self) -> bytes:
        return self.recv_messages.popleft()


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


class OrderlyWebsocketParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify websocket subscribe flows preserve algo acks and push events."""

    def test_build_topic_command_message_preserves_explicit_empty_params(self) -> None:
        """Keep intentionally empty params mappings in the outgoing payload."""
        assert build_topic_command_message("1", "subscribe", "topic", params={}) == {
            "id": "1",
            "event": "subscribe",
            "topic": "topic",
            "params": {},
        }

    async def test_subscribe_public_retries_once_when_socket_closes_before_ack(self) -> None:
        """Reconnect once for public subscribe when the socket closes during send/ack."""
        manager = _build_manager()
        first_socket = _FakeSocket(recv_messages=deque())
        second_socket = _FakeSocket(recv_messages=deque())
        closed_error = OrderlyWebsocketSubscriptionError(
            "Orderly websocket closed before acknowledgement for subscribe:subscribe-1."
        )

        manager.connect_public = AsyncMock(side_effect=[first_socket, second_socket])
        manager._subscribe_many = AsyncMock(side_effect=[closed_error, None])  # type: ignore[method-assign]
        manager._reset_public_socket = AsyncMock()  # type: ignore[method-assign]

        await manager.subscribe_public(("PERP_BTC_USDC@bbo",))

        manager._reset_public_socket.assert_awaited_once()  # type: ignore[attr-defined]
        self.assertEqual(manager.connect_public.await_count, 2)
        self.assertEqual(manager._subscribe_many.await_count, 2)  # type: ignore[attr-defined]
        assert "PERP_BTC_USDC@bbo" in manager._public_topics

    async def test_unsubscribe_public_drops_local_topics_when_socket_closes_before_ack(
        self,
    ) -> None:
        """Do not crash when public unsubscribe races with a clean socket close."""
        manager = _build_manager()
        manager._public_topics.update({"PERP_BTC_USDC@bbo", "PERP_BTC_USDC@markprice"})
        closed_error = OrderlyWebsocketSubscriptionError(
            "Orderly websocket closed before acknowledgement for unsubscribe:unsubscribe-8."
        )

        manager.connect_public = AsyncMock(return_value=_FakeSocket(recv_messages=deque()))
        manager._unsubscribe_many = AsyncMock(side_effect=closed_error)  # type: ignore[method-assign]
        manager._reset_public_socket = AsyncMock()  # type: ignore[method-assign]

        await manager.unsubscribe_public(("PERP_BTC_USDC@bbo", "PERP_BTC_USDC@markprice"))

        manager._reset_public_socket.assert_awaited_once()  # type: ignore[attr-defined]
        assert "PERP_BTC_USDC@bbo" not in manager._public_topics
        assert "PERP_BTC_USDC@markprice" not in manager._public_topics

    async def test_subscribe_private_buffers_algo_push_events_until_after_ack(self) -> None:
        """Return buffered algo push events only after the subscribe ack completes."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket(
            recv_messages=deque(
                [
                    json.dumps(
                        {
                            "topic": "algoexecutionreport",
                            "data": {"algo_order_id": "60000"},
                        },
                    ).encode("utf-8"),
                    json.dumps(
                        {"id": "subscribe-1", "event": "subscribe", "success": True},
                    ).encode("utf-8"),
                ],
            ),
        )
        manager.connect_private = AsyncMock(return_value=socket)

        # Act
        await manager.subscribe_private((ALGO_EXECUTION_REPORT_TOPIC,))
        event = await manager.next_private_event()

        # Assert
        assert socket.sent_messages == [
            {"id": "subscribe-1", "event": "subscribe", "topic": "algoexecutionreport"}
        ]
        assert event == {"topic": "algoexecutionreport", "data": {"algo_order_id": "60000"}}

    async def test_unsubscribe_private_raises_for_failed_acknowledgements(self) -> None:
        """Raise the subscription protocol error when Orderly rejects an ack."""
        # Arrange
        manager = _build_manager()
        socket = _FakeSocket(
            recv_messages=deque(
                [
                    json.dumps(
                        {
                            "id": "unsubscribe-1",
                            "event": "unsubscribe",
                            "success": False,
                            "errorMsg": "topic rejected",
                        },
                    ).encode("utf-8"),
                ],
            ),
        )
        manager.connect_private = AsyncMock(return_value=socket)

        # Act / Assert
        with self.assertRaisesRegex(OrderlyWebsocketSubscriptionError, "topic rejected"):
            await manager.unsubscribe_private((ALGO_EXECUTION_REPORT_TOPIC,))

    def test_account_topics_include_algo_execution_reports(self) -> None:
        """Keep algo execution topics in the private account subscription set."""
        # Arrange
        expected_topic = ALGO_EXECUTION_REPORT_TOPIC

        # Act
        topics = ACCOUNT_TOPICS

        # Assert
        assert expected_topic in topics
