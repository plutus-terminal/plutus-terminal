"""Centralized messgae bus."""

from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias

from PySide6.QtCore import QObject, Signal

from plutus_terminal.core.exchange.types import OrderData, PerpsPosition, PriceData
from plutus_terminal.core.news.types import NewsData

SubscribedData: TypeAlias = dict[str, PriceData]  # noqa: UP040
PositionsList: TypeAlias = list[PerpsPosition]  # noqa: UP040
OrdersList: TypeAlias = list[OrderData]  # noqa: UP040


class MessageBus(QObject):
    """Centralized message bus."""

    subscribed_prices_fetched: Signal = Signal(SubscribedData)
    """Signal emitted when price data of subscribed pairs is fetched."""

    balance_fetched: Signal = Signal(Decimal)
    """Signal emitted when current balance is fetched."""

    positions_fetched: Signal = Signal(PositionsList)
    """Signal emitted when open positions are fetched."""

    orders_feched: Signal = Signal(OrdersList)
    """Signal emitted when open orders are fetched."""

    raw_news: Signal = Signal(NewsData)
    """Signal emitted when raw news is received."""

    formatted_news: Signal = Signal(NewsData)
    """Signal emitted when formatted_news is received."""
