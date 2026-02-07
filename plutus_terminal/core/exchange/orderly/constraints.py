"""Order validation constraints for Orderly."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING

from plutus_terminal.core.exceptions import InvalidOrderSizeError

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRule


def quantize_price(price: Decimal, market_rule: OrderlyMarketRule) -> Decimal:
    """Quantize order price to quote tick size."""
    return _quantize_to_step(price, market_rule.quote_tick)


def quantize_base_size(base_size: Decimal, market_rule: OrderlyMarketRule) -> Decimal:
    """Quantize base size to market base tick."""
    return _quantize_to_step(base_size, market_rule.base_tick)


def validate_order_size(
    *,
    base_size: Decimal,
    limit_price: Decimal,
    market_rule: OrderlyMarketRule,
) -> None:
    """Validate order base size and notional constraints."""
    if base_size <= Decimal(0):
        msg = "Order size must be greater than zero."
        raise InvalidOrderSizeError(msg)
    if base_size < market_rule.base_min:
        msg = f"Order base size too small. Minimum is {market_rule.base_min}."
        raise InvalidOrderSizeError(msg)
    if base_size > market_rule.base_max:
        msg = f"Order base size too large. Maximum is {market_rule.base_max}."
        raise InvalidOrderSizeError(msg)

    notional = base_size * limit_price
    if notional < market_rule.min_notional:
        msg = f"Order notional too small. Minimum is {market_rule.min_notional}."
        raise InvalidOrderSizeError(msg)


def _quantize_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round down value to nearest multiple of step."""
    if step <= Decimal(0):
        return value
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step
