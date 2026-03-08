"""Models for Orderly exchange integration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.types import PerpsTradeType


class OrderlyNetwork(StrEnum):
    """Supported Orderly environments."""

    MAINNET = "mainnet"
    TESTNET = "testnet"


@dataclass(frozen=True, slots=True)
class OrderlyCredentials:
    """Credentials used for Orderly private endpoints."""

    account_id: str
    orderly_key: str
    orderly_secret: str


@dataclass(frozen=True, slots=True)
class OrderlyEndpoints:
    """Orderly REST and websocket base URLs."""

    rest_url: str
    public_ws_url: str
    private_ws_url: str


def endpoints_for_network(network: OrderlyNetwork) -> OrderlyEndpoints:
    """Return endpoint URLs for the selected network."""
    if network is OrderlyNetwork.TESTNET:
        return OrderlyEndpoints(
            rest_url="https://testnet-api.orderly.org",
            public_ws_url="wss://testnet-ws-evm.orderly.org/ws/stream",
            private_ws_url="wss://testnet-ws-private-evm.orderly.org/v2/ws/private/stream",
        )

    return OrderlyEndpoints(
        rest_url="https://api.orderly.org",
        public_ws_url="wss://ws-evm.orderly.org/ws/stream",
        private_ws_url="wss://ws-private-evm.orderly.org/v2/ws/private/stream",
    )


class OrderlyApiErrorBody(TypedDict, total=False):
    """Error body shape returned by Orderly API."""

    code: int
    message: str
    success: bool
    data: Any


class OrderlySide(StrEnum):
    """Orderly order side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderlyOrderType(StrEnum):
    """Supported native Orderly execution types used by Plutus."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderlyAlgoType(StrEnum):
    """Orderly algo order families used by Plutus."""

    STOP = "STOP"
    TP_SL = "TP_SL"


class OrderlyTpSlChildType(StrEnum):
    """Orderly child algo variants for TP/SL orders."""

    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


class OrderlyTriggerPriceType(StrEnum):
    """Trigger price source supported by Orderly conditional orders."""

    MARK_PRICE = "MARK_PRICE"


@dataclass(frozen=True, slots=True)
class OrderlyOrderRequest:
    """Normalized request used to build native Orderly order payloads.

    Quantity is always expressed in base units after market-rule quantization.
    Trade direction refers to the position direction; reduce-only requests flip the
    outgoing Orderly side so exit orders close the existing exposure.
    """

    symbol: str
    trade_type: PerpsTradeType
    side: OrderlySide
    quantity: Decimal
    reduce_only: bool
    price: Decimal | None = None
    trigger_price: Decimal | None = None
    trigger_price_type: OrderlyTriggerPriceType = OrderlyTriggerPriceType.MARK_PRICE
    take_profit: Decimal = Decimal(0)
    stop_loss: Decimal = Decimal(0)

    @property
    def has_take_profit(self) -> bool:
        """Return whether request includes a take-profit target."""
        return self.take_profit > Decimal(0)

    @property
    def has_stop_loss(self) -> bool:
        """Return whether request includes a stop-loss target."""
        return self.stop_loss > Decimal(0)

    @property
    def has_any_tp_sl(self) -> bool:
        """Return whether request includes any TP/SL target."""
        return self.has_take_profit or self.has_stop_loss


class OrderlyRegularOrderPayload(TypedDict):
    """Regular `/v1/order` payload."""

    symbol: str
    side: str
    order_type: str
    order_quantity: str
    client_order_id: str
    reduce_only: bool
    order_price: NotRequired[str]


class OrderlyStopOrderPayload(TypedDict):
    """Conditional `STOP` `/v1/algo/order` payload."""

    symbol: str
    side: str
    algo_type: str
    type: str
    quantity: str
    trigger_price: str
    trigger_price_type: str
    reduce_only: bool
    price: NotRequired[str]


class OrderlyTpSlChildOrderPayload(TypedDict):
    """Child order within a native Orderly `TP_SL` payload."""

    algo_type: str
    type: str
    trigger_price: str
    trigger_price_type: str
    reduce_only: bool
    price: NotRequired[str]


class OrderlyTpSlOrderPayload(TypedDict):
    """Algo `/v1/algo/order` TP/SL payload."""

    symbol: str
    side: str
    algo_type: str
    quantity: str
    child_orders: list[OrderlyTpSlChildOrderPayload]


class OrderlyRegularOrderRow(TypedDict, total=False):
    """Regular `/v1/orders` response row used by parser code."""

    order_id: int | str
    client_order_id: str
    symbol: str
    side: str
    status: str
    order_type: str
    price: str
    order_price: str
    quantity: str
    order_quantity: str
    amount: str
    order_amount: str
    total_fee: str
    fee_asset: str
    realized_pnl: str
    reduce_only: bool
    created_time: int | str
    updated_time: int | str


class OrderlyAlgoChildOrderRow(TypedDict, total=False):
    """Child order entry nested under a native TP/SL algo order."""

    algo_order_id: int | str
    parent_algo_order_id: int | str
    root_algo_order_id: int | str
    algo_type: str
    algo_status: str
    root_algo_order_status: str
    type: str
    trigger_price: str
    trigger_price_type: str
    price: str
    reduce_only: bool
    created_time: int | str
    updated_time: int | str


class OrderlyAlgoOrderRow(TypedDict, total=False):
    """Algo `/v1/algo/orders` response row used by parser code."""

    algo_order_id: int | str
    root_algo_order_id: int | str
    parent_algo_order_id: int | str
    symbol: str
    side: str
    algo_type: str
    algo_status: str
    root_algo_order_status: str
    type: str
    quantity: str
    trigger_price: str
    trigger_price_type: str
    price: str
    total_fee: str
    fee_asset: str
    realized_pnl: str
    reduce_only: bool
    is_triggered: bool
    triggered: bool
    child_orders: list[OrderlyAlgoChildOrderRow]
    created_time: int | str
    updated_time: int | str


class OrderlyPositionRow(TypedDict, total=False):
    """Native position row fields consumed by fetcher parsing."""

    symbol: str
    position_id: int | str
    position_qty: str
    average_open_price: str
    mark_price: str
    cost_position: str
    leverage: str
    est_liq_price: str
    est_liquidation_price: str
    liquidation_price: str
    liq_price: str
    imr: str
    imr_with_orders: str
    IMR_withdraw_orders: str
    mmr: str
    mmr_with_orders: str
    MMR_with_orders: str
    unsettled_pnl: str
    timestamp: str
    updated_time: str
    pnl_24_h: str
    fee_24_h: str
    funding_fee: str
    last_sum_unitary_funding: str
    pending_long_qty: str
    pending_short_qty: str
    settle_price: str
