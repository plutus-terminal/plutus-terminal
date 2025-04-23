"""Types for exachanges."""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import TYPE_CHECKING, NotRequired, Optional, TypedDict

from hexbytes import HexBytes

if TYPE_CHECKING:
    from decimal import Decimal

    from eth_typing import ChecksumAddress
    from pandas import Timestamp

TradeResults = HexBytes | dict


class ExchangeType(IntEnum):
    """Exchange type."""

    DEX = 0


class PerpsTradeType(IntEnum):
    """Trade Types."""

    MARKET = 0
    LIMIT = 1
    STOP_MARKET = 2
    STOP_LIMIT = 3
    TRIGGER_TP = 4
    TRIGGER_SL = 5


class PerpsTradeDirection(Enum):
    """Trade direction."""

    SHORT = False
    LONG = True


class PriceData(TypedDict):
    """PriceData from exchange."""

    price: Decimal
    date: Timestamp
    volume: NotRequired[float]


class PriceHistory(TypedDict):
    """Price history from exchange dict."""

    date: list[Timestamp]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: NotRequired[float]


class PerpsPosition(TypedDict):
    """Trade position from exchange."""

    pair: str
    id: int
    position_size_stable: Decimal
    collateral_stable: Decimal
    open_price: Decimal
    trade_direction: PerpsTradeDirection
    leverage: Decimal
    liquidation_price: Decimal
    extra: NotRequired[dict]


class PnlDetails(TypedDict):
    """Pnl details from exchange."""

    pnl_usd_before_fees: Decimal
    pnl_percentage_before_fees: Decimal
    funding_fee_usd: Decimal
    position_fee_usd: Decimal
    pnl_usd_after_fees: Decimal
    pnl_percentage_after_fees: Decimal


class OrderData(TypedDict):
    """Order data from exchange."""

    id: str
    pair: str
    trigger_price: Decimal
    size_stable: Decimal
    trade_direction: PerpsTradeDirection
    order_type: PerpsTradeType
    reduce_only: bool
    extra: NotRequired[dict]


class NewAccountInfo(TypedDict):
    """New account info."""

    referral_link: NotRequired[Optional[str]]
    secrets: list[str]
