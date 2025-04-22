"""Centralized messgae bus."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from plutus_terminal.core.news.types import NewsData


class MessageBus(QObject):
    """Centralized message bus."""

    subscribed_prices_fetched: Signal = Signal(dict)
    """Signal emitted when price data of subscribed pairs is fetched.

    Args:
        dict[str, PriceData]: Dict with pair and price data.
    """

    balance_fetched: Signal = Signal(Decimal)
    """Signal emitted when current balance is fetched."""

    positions_fetched: Signal = Signal(list)
    """Signal emitted when open positions are fetched.

    Args:
        list[PerpsPosition]: List of open positions.
    """

    orders_fetched: Signal = Signal(list)
    """Signal emitted when open orders are fetched.

    Args:
        list[OrderData]: List of open orders.
    """

    raw_news: Signal = Signal(NewsData)
    """Signal emitted when raw news is received."""

    formatted_news: Signal = Signal(NewsData)
    """Signal emitted when formatted_news is received."""
