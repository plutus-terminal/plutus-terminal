"""Topic helpers for Orderly websocket streams."""

from __future__ import annotations

USDC_SETTLEMENT_TOKEN = "USDC"  # noqa: S105


def mark_price_topic(symbol: str) -> str:
    """Build mark price topic for a specific symbol."""
    return f"{symbol}@markprice"


def bbo_topic(symbol: str) -> str:
    """Build best bid/offer topic for a specific symbol."""
    return f"{symbol}@bbo"


ACCOUNT_TOPICS: tuple[str, ...] = (
    "account",
    "balance",
    "executionreport",
    "position",
)
