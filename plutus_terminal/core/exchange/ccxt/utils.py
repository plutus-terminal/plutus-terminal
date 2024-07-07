"""CCXT Utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from decimal import Decimal

    from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType


class TradingArgs(TypedDict):
    """Args for trading with CCXT."""

    pair: str
    trade_type: PerpsTradeType
    side: PerpsTradeDirection
    amount: Decimal
    price: Decimal
    take_profit: NotRequired[Decimal]
    stop_loss: NotRequired[Decimal]
