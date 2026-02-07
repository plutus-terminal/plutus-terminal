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
from plutus_terminal.core.exchange.types import PerpsTradeDirection, PerpsTradeType, TradeResults

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
        symbol = str(trade_arguments["symbol"])
        direction = PerpsTradeDirection(trade_arguments["trade_direction"])
        trade_type = PerpsTradeType(trade_arguments["trade_type"])
        limit_price = Decimal(str(trade_arguments["price"]))
        reduce_only = bool(trade_arguments.get("reduce_only", False))

        market_rule = self._market_registry.get_rule_by_symbol(symbol)
        order_price = quantize_price(limit_price, market_rule)
        base_size = _resolve_base_size(trade_arguments, order_price, market_rule)
        validate_order_size(base_size=base_size, limit_price=order_price, market_rule=market_rule)

        body = {
            "symbol": symbol,
            "side": _side_for_direction(direction),
            "order_type": _order_type(trade_type),
            "order_price": str(order_price),
            "order_quantity": str(base_size),
            "reduce_only": reduce_only,
            "client_order_id": f"plutus_{uuid4().hex[:24]}",
        }

        if trade_type is PerpsTradeType.MARKET:
            body.pop("order_price")

        try:
            return await self._rest_client.request_private("POST", "/v1/order", json_body=body)
        except Exception as error:
            raise TransactionFailedError from error

    async def create_reduce_order(self, trade_arguments: dict) -> TradeResults:
        """Create reduce-only order for an existing position."""
        order_args = dict(trade_arguments)
        order_args["reduce_only"] = True
        return await self.create_order(order_args)

    async def close_position(self, trade_arguments: dict) -> TradeResults:
        """Close position with a reduce-only market order."""
        direction = PerpsTradeDirection(trade_arguments["trade_direction"])
        close_args = dict(trade_arguments)
        close_args["trade_type"] = PerpsTradeType.MARKET
        close_args["reduce_only"] = True
        close_args["trade_direction"] = _opposite_direction(direction)
        return await self.create_order(close_args)

    async def cancel_order(self, trade_arguments: dict) -> TradeResults:
        """Cancel one order by id and symbol."""
        params = {
            "order_id": str(trade_arguments["order_id"]),
            "symbol": str(trade_arguments["symbol"]),
        }
        try:
            return await self._rest_client.request_private("DELETE", "/v1/order", params=params)
        except Exception as error:
            raise TransactionFailedError from error

    async def edit_order(self, trade_arguments: dict) -> TradeResults:
        """Edit order by replacing existing one (cancel then create)."""
        cancel_result = await self.cancel_order(
            {
                "order_id": trade_arguments["order_id"],
                "symbol": trade_arguments["symbol"],
            },
        )
        create_result = await self.create_order(trade_arguments)
        return {"cancel": cancel_result, "create": create_result}

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


def _order_type(trade_type: PerpsTradeType) -> str:
    """Map internal trade type to Orderly order type."""
    if trade_type is PerpsTradeType.MARKET:
        return "MARKET"
    return "LIMIT"


def _side_for_direction(direction: PerpsTradeDirection) -> str:
    """Map direction to Orderly side."""
    if direction is PerpsTradeDirection.LONG:
        return "BUY"
    return "SELL"


def _opposite_direction(direction: PerpsTradeDirection) -> PerpsTradeDirection:
    """Return opposite direction from current position direction."""
    if direction is PerpsTradeDirection.LONG:
        return PerpsTradeDirection.SHORT
    return PerpsTradeDirection.LONG


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
