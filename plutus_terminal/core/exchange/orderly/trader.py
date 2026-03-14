"""Trader implementation for Orderly exchange."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.orderly.constraints import (
    quantize_base_size,
    quantize_price,
    validate_order_size,
)
from plutus_terminal.core.exchange.orderly.models import (
    OrderlyAlgoType,
    OrderlyOrderRequest,
    OrderlyOrderType,
    OrderlyRegularOrderPayload,
    OrderlySide,
    OrderlyStopOrderPayload,
    OrderlyTpSlChildOrderPayload,
    OrderlyTpSlChildType,
    OrderlyTpSlOrderPayload,
)
from plutus_terminal.core.exchange.types import (
    PerpsTradeDirection,
    PerpsTradeType,
    TradeResults,
)

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.markets import (
        OrderlyMarketRegistry,
        OrderlyMarketRule,
    )
    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient


class OrderlyTrader:
    """Send order operations to Orderly private REST endpoints."""

    def __init__(
        self,
        rest_client: OrderlyRestClient,
        market_registry: OrderlyMarketRegistry,
    ) -> None:
        """Initialize trader with API client and market metadata."""
        self._rest_client = rest_client
        self._market_registry = market_registry

    async def create_order(self, trade_arguments: dict) -> TradeResults:
        """Create order from normalized trade arguments."""
        request = _build_order_request(trade_arguments, self._market_registry)

        try:
            primary_result = await self._submit_order_request(request)
        except Exception as error:
            raise TransactionFailedError from error

        result: TradeResults = primary_result
        if request.trade_type.is_regular_order and request.has_any_tp_sl:
            try:
                tp_sl_result = await self._rest_client.request_private(
                    "POST",
                    "/v1/algo/order",
                    json_body=_build_tp_sl_order_payload(request),
                )
                result = {"primary": primary_result, "tp_sl": tp_sl_result}
            except Exception as error:
                result = {
                    "primary": primary_result,
                    "tp_sl": None,
                    "partial_success": True,
                    "tp_sl_error": str(error),
                }
        return result

    async def create_reduce_order(self, trade_arguments: dict) -> TradeResults:
        """Create reduce-only order for an existing position."""
        order_args = dict(trade_arguments)
        order_args["reduce_only"] = True
        if order_args["trade_type"] in (PerpsTradeType.TRIGGER_TP, PerpsTradeType.TRIGGER_SL):
            trigger_request = _build_order_request(order_args, self._market_registry)
            try:
                return await self._rest_client.request_private(
                    "POST",
                    "/v1/algo/order",
                    json_body=_build_tp_sl_order_payload(trigger_request),
                )
            except Exception as error:
                raise TransactionFailedError from error
        return await self.create_order(order_args)

    async def close_position(self, trade_arguments: dict) -> TradeResults:
        """Close position with a reduce-only market order."""
        close_args = dict(trade_arguments)
        close_args["trade_type"] = PerpsTradeType.MARKET
        close_args["reduce_only"] = True
        return await self.create_order(close_args)

    async def cancel_order(self, trade_arguments: dict) -> TradeResults:
        """Cancel one order by id and symbol."""
        trade_type = PerpsTradeType(trade_arguments.get("trade_type", PerpsTradeType.LIMIT))
        params = {
            "order_id": str(trade_arguments["order_id"]),
            "symbol": str(trade_arguments["symbol"]),
        }
        path = "/v1/algo/order" if not trade_type.is_regular_order else "/v1/order"
        try:
            return await self._rest_client.request_private("DELETE", path, params=params)
        except Exception as error:
            raise TransactionFailedError from error

    async def edit_order(self, trade_arguments: dict) -> TradeResults:
        """Edit one order through Orderly native PUT endpoints."""
        trade_type = PerpsTradeType(trade_arguments["trade_type"])
        request = _build_order_request(trade_arguments, self._market_registry)
        order_id = str(trade_arguments["order_id"])

        if trade_type.is_regular_order:
            path = "/v1/order"
            payload = _build_regular_edit_payload(order_id, request)
        elif trade_type.is_stop_order:
            path = "/v1/algo/order"
            payload = _build_stop_edit_payload(order_id, request)
        else:
            path = "/v1/algo/order"
            payload = _build_tp_sl_edit_payload(order_id, request)

        try:
            return await self._rest_client.request_private("PUT", path, json_body=payload)
        except Exception as error:
            raise TransactionFailedError from error

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for one symbol."""
        body = {"symbol": symbol, "leverage": leverage}
        try:
            return await self._rest_client.request_private(
                "POST",
                "/v1/client/leverage",
                json_body=body,
            )
        except Exception as error:
            raise TransactionFailedError from error

    async def _submit_order_request(self, request: OrderlyOrderRequest) -> TradeResults:
        """Send one native Orderly order request."""
        if request.trade_type.is_stop_order:
            return await self._rest_client.request_private(
                "POST",
                "/v1/algo/order",
                json_body=_build_stop_order_payload(request),
            )
        return await self._rest_client.request_private(
            "POST",
            "/v1/order",
            json_body=_build_regular_order_payload(request),
        )


def _build_order_request(
    trade_arguments: dict,
    market_registry: OrderlyMarketRegistry,
) -> OrderlyOrderRequest:
    """Normalize trade arguments into a native Orderly request model."""
    symbol = str(trade_arguments["symbol"])
    direction = PerpsTradeDirection(trade_arguments["trade_direction"])
    trade_type = PerpsTradeType(trade_arguments["trade_type"])
    reduce_only = bool(trade_arguments.get("reduce_only", False))
    market_rule = market_registry.get_rule_by_symbol(symbol)

    price = _resolve_price(trade_arguments, market_rule)
    quantity = _resolve_base_size(trade_arguments, price, market_rule)
    validate_order_size(base_size=quantity, limit_price=price, market_rule=market_rule)

    trigger_price = trade_arguments.get("trigger_price")
    if trigger_price is None and trade_type in (
        PerpsTradeType.STOP_MARKET,
        PerpsTradeType.STOP_LIMIT,
    ):
        trigger_price = trade_arguments.get("price")

    return OrderlyOrderRequest(
        symbol=symbol,
        trade_type=trade_type,
        side=_side_for_trade(direction, reduce_only),
        quantity=quantity,
        reduce_only=reduce_only,
        price=_optional_quantized_price(trade_arguments.get("price"), market_rule),
        trigger_price=_optional_quantized_price(trigger_price, market_rule),
        take_profit=_optional_quantized_price(trade_arguments.get("take_profit"), market_rule)
        or Decimal(0),
        stop_loss=_optional_quantized_price(trade_arguments.get("stop_loss"), market_rule)
        or Decimal(0),
    )


def _build_regular_order_payload(request: OrderlyOrderRequest) -> OrderlyRegularOrderPayload:
    """Build `/v1/order` payload for regular market or limit orders."""
    body: OrderlyRegularOrderPayload = {
        "symbol": request.symbol,
        "side": request.side.value,
        "order_type": _native_order_type(request.trade_type).value,
        "order_quantity": str(request.quantity),
        "reduce_only": request.reduce_only,
        "client_order_id": f"plutus_{uuid4().hex[:24]}",
    }
    if request.price is not None and request.trade_type is not PerpsTradeType.MARKET:
        body["order_price"] = str(request.price)
    return body


def _build_regular_edit_payload(
    order_id: str, request: OrderlyOrderRequest
) -> dict[str, str | bool]:
    """Build `/v1/order` edit payload for a pending regular order."""
    body: dict[str, str | bool] = {
        "order_id": order_id,
        "symbol": request.symbol,
        "side": request.side.value,
        "order_type": _native_order_type(request.trade_type).value,
        "order_quantity": str(request.quantity),
        "reduce_only": request.reduce_only,
    }
    if request.price is not None and request.trade_type is not PerpsTradeType.MARKET:
        body["order_price"] = str(request.price)
    return body


def _build_stop_order_payload(request: OrderlyOrderRequest) -> OrderlyStopOrderPayload:
    """Build native Orderly `STOP` algo payload."""
    if request.trigger_price is None:
        msg = "Stop orders require a trigger price."
        raise ValueError(msg)

    body: OrderlyStopOrderPayload = {
        "symbol": request.symbol,
        "side": request.side.value,
        "algo_type": OrderlyAlgoType.STOP.value,
        "type": _native_order_type(request.trade_type).value,
        "quantity": str(request.quantity),
        "trigger_price": str(request.trigger_price),
        "trigger_price_type": request.trigger_price_type.value,
        "reduce_only": request.reduce_only,
    }
    if request.price is not None and request.trade_type is PerpsTradeType.STOP_LIMIT:
        body["price"] = str(request.price)
    return body


def _build_stop_edit_payload(order_id: str, request: OrderlyOrderRequest) -> dict[str, object]:
    """Build `/v1/algo/order` edit payload for a pending stop order."""
    body = dict(_build_stop_order_payload(request))
    body["order_id"] = order_id
    return body


def _build_tp_sl_order_payload(request: OrderlyOrderRequest) -> OrderlyTpSlOrderPayload:
    """Build native Orderly `TP_SL` payload for one or two child orders."""
    child_orders: list[OrderlyTpSlChildOrderPayload] = []
    if request.has_take_profit:
        child_orders.append(
            _build_tp_sl_child_order(
                request,
                OrderlyTpSlChildType.TAKE_PROFIT,
                request.take_profit,
            ),
        )
    if request.has_stop_loss:
        child_orders.append(
            _build_tp_sl_child_order(
                request,
                OrderlyTpSlChildType.STOP_LOSS,
                request.stop_loss,
            ),
        )
    if not child_orders:
        msg = "TP/SL algo orders require at least one trigger target."
        raise ValueError(msg)

    side = request.side
    if not request.reduce_only:
        side = OrderlySide.SELL if request.side is OrderlySide.BUY else OrderlySide.BUY

    return {
        "symbol": request.symbol,
        "side": side.value,
        "algo_type": OrderlyAlgoType.TP_SL.value,
        "quantity": str(request.quantity),
        "child_orders": child_orders,
    }


def _build_tp_sl_edit_payload(order_id: str, request: OrderlyOrderRequest) -> dict[str, object]:
    """Build `/v1/algo/order` edit payload for an existing TP/SL root order."""
    body = dict(_build_tp_sl_order_payload(request))
    body["order_id"] = order_id
    return body


def _build_tp_sl_child_order(
    request: OrderlyOrderRequest,
    child_type: OrderlyTpSlChildType,
    trigger_price: Decimal,
) -> OrderlyTpSlChildOrderPayload:
    """Build a child order for native Orderly TP/SL algo requests."""
    return {
        "algo_type": child_type.value,
        "type": OrderlyOrderType.MARKET.value,
        "trigger_price": str(trigger_price),
        "trigger_price_type": request.trigger_price_type.value,
        "reduce_only": True,
    }


def _native_order_type(trade_type: PerpsTradeType) -> OrderlyOrderType:
    """Map internal trade type to native Orderly execution type."""
    if trade_type in (PerpsTradeType.MARKET, PerpsTradeType.STOP_MARKET):
        return OrderlyOrderType.MARKET
    return OrderlyOrderType.LIMIT


def _side_for_trade(
    direction: PerpsTradeDirection,
    reduce_only: bool,
) -> OrderlySide:
    """Map position direction and reduce-only semantics to Orderly side."""
    if reduce_only:
        direction = _opposite_direction(direction)
    if direction is PerpsTradeDirection.LONG:
        return OrderlySide.BUY
    return OrderlySide.SELL


def _opposite_direction(direction: PerpsTradeDirection) -> PerpsTradeDirection:
    """Return opposite direction from current position direction."""
    if direction is PerpsTradeDirection.LONG:
        return PerpsTradeDirection.SHORT
    return PerpsTradeDirection.LONG


def _resolve_price(
    trade_arguments: dict,
    market_rule: OrderlyMarketRule,
) -> Decimal:
    """Resolve price used for validation and quantity conversion."""
    raw_price = trade_arguments.get("price")
    if raw_price is None:
        msg = "Orderly order requests require a price for size validation."
        raise ValueError(msg)
    return quantize_price(Decimal(str(raw_price)), market_rule)


def _optional_quantized_price(
    raw_price: object | None,
    market_rule: OrderlyMarketRule,
) -> Decimal | None:
    """Quantize optional price fields when present."""
    if raw_price is None:
        return None
    text = str(raw_price).strip()
    if text == "":
        return None
    return quantize_price(Decimal(text), market_rule)


def _resolve_base_size(
    trade_arguments: dict,
    order_price: Decimal,
    market_rule: OrderlyMarketRule,
) -> Decimal:
    """Resolve order base size from explicit quantity or stable notional."""
    explicit_base_size = trade_arguments.get("base_size")
    if explicit_base_size is not None:
        return quantize_base_size(Decimal(str(explicit_base_size)), market_rule)

    size_stable = Decimal(str(trade_arguments["size_stable"]))
    return quantize_base_size(size_stable / order_price, market_rule)
