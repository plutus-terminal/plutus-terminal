"""Exchange helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exchange.types import PerpsTradeDirection


def get_take_profit_target(
    execution_price: Decimal,
    take_profit_percent: Optional[float],
    trade_direction: PerpsTradeDirection,
) -> Decimal:
    """Get take profit target price."""
    if take_profit_percent is None:
        take_profit_percent = CONFIG.take_profit

    if take_profit_percent == 0:
        return Decimal(0)

    if trade_direction == PerpsTradeDirection.LONG:
        return execution_price * (1 + Decimal(take_profit_percent) / 100)
    return execution_price * (1 - Decimal(take_profit_percent) / 100)


def get_stop_loss_target(
    execution_price: Decimal,
    take_profit_percent: Optional[float],
    trade_direction: PerpsTradeDirection,
) -> Decimal:
    """Get stop loss target price."""
    if take_profit_percent is None:
        take_profit_percent = CONFIG.stop_loss

    if take_profit_percent == 0:
        return Decimal(0)

    if trade_direction == PerpsTradeDirection.LONG:
        return execution_price * (1 - Decimal(take_profit_percent) / 100)
    return execution_price * (1 + Decimal(take_profit_percent) / 100)
