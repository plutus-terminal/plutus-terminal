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


class OptionsSortingBy(Enum):
    """Sorting by filters for options."""

    RATE = "rate"
    RESERVED = "reserved"
    AVAILABLE = "available"
    DURATION = "duration"
    PERCENT = "percent"
    AMOUNT = "AMOUNT"

    def __str__(self) -> str:
        """Override str to return value."""
        return self.value


class OptionsSortingDestination(Enum):
    """Sorting destination filter for options based on sortingBy."""

    ASC = "ASC"
    DESC = "DESC"

    def __str__(self) -> str:
        """Override str to return value."""
        return self.value


class OptionsOrderType(Enum):
    """Order type for options."""

    MY_ORDER = "my_order"
    ALL_ORDER = "all_order"

    def __str__(self) -> str:
        """Override str to return value."""
        return self.value


class OptionsDirection(Enum):
    """Options direction."""

    UP = "up"
    DOWN = "down"

    def __str__(self) -> str:
        """Override str to return value."""
        return self.value


class OptionsDuration(IntEnum):
    """Duration argument for Options."""

    M15 = 15 * 60
    M30 = 30 * 60
    H1 = 60 * 60
    H2 = 2 * 60 * 60
    H4 = 4 * 60 * 60
    H8 = 8 * 60 * 60
    H24 = 24 * 60 * 60


class OptionsPercent(IntEnum):
    """Percent for options."""

    UP = 1000000100000000000
    UP_010 = 1001000000000000000
    UP_025 = 1002500000000000000
    UP_050 = 1005000000000000000
    UP_1 = 1010000000000000000
    UP_3 = 1030000000000000000
    UP_5 = 1050000000000000000
    DOWN = 999999900000000000
    DOWN_010 = 999000000000000000
    DOWN_025 = 997500000000000000
    DOWN_050 = 995000000000000000
    DOWN_1 = 990000000000000000
    DOWN_3 = 970000000000000000
    DOWN_5 = 950000000000000000


class OptionsOrdersParams(TypedDict, total=False):
    """Params for options orders query."""

    oracle_ids: Optional[list[int]]
    sorting_by: Optional[OptionsSortingBy]
    sorting_destination: Optional[OptionsSortingDestination]
    closed: Optional[bool]
    account: Optional[ChecksumAddress]
    order_type: Optional[OptionsOrderType]
    duration: Optional[OptionsDuration]
    percent: Optional[str]
    skip: Optional[int]
    limit: Optional[int]


class OptionsRisk(Enum):
    """Options risks strategy."""

    PRIO_RETURN = 0
    PRIO_SAFETY = 1


class OptionsStrategy(TypedDict):
    """Strategy params for options buy."""

    rate_min: float
    available_min: float
    percent_min: OptionsPercent
    percent_max: OptionsPercent
    duration_min: OptionsDuration
    duration_max: OptionsDuration
    risk: OptionsRisk
    direction: OptionsDirection


class OptionsBuyParams(TypedDict):
    """Buy params for options."""

    orders: dict[int, int]
    price_id: str


class NewAccountInfo(TypedDict):
    """New account info."""

    referral_link: NotRequired[Optional[str]]
    secrets: list[str]
