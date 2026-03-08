"""Topic helpers for Orderly websocket streams."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

USDC_SETTLEMENT_TOKEN = "USDC"  # noqa: S105
EXECUTION_REPORT_TOPIC = "executionreport"
ALGO_EXECUTION_REPORT_TOPIC = "algoexecutionreport"
ACKABLE_WS_EVENTS = frozenset({"auth", "subscribe", "unsubscribe"})


def mark_price_topic(symbol: str) -> str:
    """Build mark price topic for a specific symbol."""
    return f"{symbol}@markprice"


def bbo_topic(symbol: str) -> str:
    """Build best bid/offer topic for a specific symbol."""
    return f"{symbol}@bbo"


ACCOUNT_TOPICS: tuple[str, ...] = (
    "account",
    "balance",
    EXECUTION_REPORT_TOPIC,
    ALGO_EXECUTION_REPORT_TOPIC,
    "position",
)


def build_topic_command_message(
    request_id: str,
    event: str,
    topic: str,
    *,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build websocket command payload for topic subscribe/unsubscribe calls."""
    payload: dict[str, Any] = {"id": request_id, "event": event, "topic": topic}
    if params:
        payload["params"] = dict(params)
    return payload
