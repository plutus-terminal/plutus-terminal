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

    @property
    def order_family(self) -> str:
        """Return the generic order family for the trade type.

        This keeps the shared trade type as the single source of truth while still
        allowing exchange adapters to branch on broader families such as regular,
        stop, or TP/SL orders. Future trade types can extend this mapping without
        introducing exchange-specific order kind fields.
        """
        if self in {self.STOP_MARKET, self.STOP_LIMIT}:
            return "stop"
        if self in {self.TRIGGER_TP, self.TRIGGER_SL}:
            return "tp_sl"
        return "regular"

    @property
    def is_regular_order(self) -> bool:
        """Return whether the trade type uses the regular order flow."""
        return self.order_family == "regular"

    @property
    def is_stop_order(self) -> bool:
        """Return whether the trade type belongs to the stop-order family."""
        return self.order_family == "stop"

    @property
    def is_tp_sl_order(self) -> bool:
        """Return whether the trade type belongs to the TP/SL family."""
        return self.order_family == "tp_sl"


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
    opening_fee_usd: Decimal
    closing_fee_usd: Decimal
    pnl_usd_after_fees: Decimal
    pnl_percentage_after_fees: Decimal
    funding_fee_included_in_pnl: NotRequired[bool]
    opening_fee_included_in_pnl: NotRequired[bool]
    pnl_label: NotRequired[str]
    net_pnl_label: NotRequired[str]
    show_closing_fee: NotRequired[bool]


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
