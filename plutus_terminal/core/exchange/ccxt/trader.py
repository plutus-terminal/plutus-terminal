"""Base trader for CCXT."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import ccxt.pro

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.base import ExchangeTrader
from plutus_terminal.core.types_ import PerpsTradeDirection

if TYPE_CHECKING:
    import plutus_terminal.core.exchange.ccxt.utils as ccxt_utils
    from plutus_terminal.core.exchange.types import TradeResults

LOGGER = logging.getLogger(__name__)


class CCXTTrader(ExchangeTrader):
    """Base trader for CCXT."""

    def __init__(self, exchange_instance: ccxt.pro.Exchange) -> None:
        """Initialize shared attributes."""
        self._cctx = exchange_instance

    async def create_order(
        self,
        trade_arguments: ccxt_utils.TradingArgs,
    ) -> TradeResults:
        """Create new order.

        Args:
            trade_arguments (ccxt.utils.TradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        LOGGER.info("Opening new position: %s", trade_arguments)
        side = "buy" if trade_arguments["side"] == PerpsTradeDirection.LONG else "sell"
        trade_type = trade_arguments["trade_type"].name.lower()
        params = {}

        # Add stop loss and take profit if available
        try:
            if trade_arguments["take_profit"] != trade_arguments["price"]:
                params["takeProfit"] = {
                    "type": "market",
                    "triggerPrice": float(trade_arguments["take_profit"]),
                }
        except KeyError:
            pass
        try:
            if trade_arguments["stop_loss"] != trade_arguments["price"]:
                params["stopLoss"] = {
                    "type": "market",
                    "triggerPrice": float(trade_arguments["stop_loss"]),
                }
        except KeyError:
            pass

        try:
            result = await self._cctx.create_order(
                symbol=trade_arguments["pair"],
                type=trade_type,  # type: ignore
                side=side,
                amount=float(trade_arguments["amount"]),
                price=float(trade_arguments["price"]),
                params=params,
            )
        except (
            ccxt.InsufficientFunds,
            ccxt.NetworkError,
        ) as error:
            raise TransactionFailedError from error

        LOGGER.info("Opened position. Result: %s", result)
        return result

    async def close_position(self, trade_arguments: dict) -> TradeResults:
        """Close the give position.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        try:
            result = await self._cctx.close_position(
                symbol=trade_arguments["pair"],
            )
        except (
            ccxt.InsufficientFunds,
            ccxt.NetworkError,
        ) as error:
            raise TransactionFailedError from error

        LOGGER.info("Closed position. Result: %s", result)
        return result

    async def cancel_order(self, trade_arguments: dict) -> TradeResults:
        """Cancel the given order.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """

    async def edit_order(
        self,
        trade_arguments: dict,
    ) -> TradeResults:
        """Update the given order.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
