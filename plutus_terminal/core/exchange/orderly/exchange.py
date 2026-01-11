"""Orderly Exchange."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Self

from qasync import asyncSlot

from plutus_terminal.core import keyring_manager
from plutus_terminal.core.exceptions import (
    InvalidOrderSizeError,
    TransactionFailedError,
)
from plutus_terminal.core.exchange.base import ExchangeBase
from plutus_terminal.core.exchange.orderly.fetcher import OrderlyFetcher
from plutus_terminal.core.exchange.orderly.trader import OrderlyTrader
from plutus_terminal.core.types_ import (
    ExchangeType,
    MessageLevel,
    NewAccountInfo,
    PerpsTradeDirection,
    PerpsTradeType,
    UserMessage,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from plutus_terminal.core.config import AppConfig
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
    from plutus_terminal.core.password_guard import PasswordGuard
    from plutus_terminal.message_bus import MessageBus


LOGGER = logging.getLogger(__name__)


class OrderlyExchange(ExchangeBase):
    """Class to interact with Orderly Exchange."""

    def __init__(
        self,
        message_bus: MessageBus,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(message_bus=message_bus, pass_guard=pass_guard, app_config=app_config)

        # Get current account credentials
        keyring_account = self.app_config.current_keyring_account
        secrets = keyring_manager.get_exchange_password(
            str(keyring_account.username), pass_guard
        )

        if len(secrets) < 2:
            LOGGER.error("Insufficient secrets for Orderly exchange")
            self.account_id = ""
            self.private_key = ""
        else:
            self.account_id = secrets[0]
            self.private_key = secrets[1]

        self._pair_prefix = "PERP_"
        self._pair_separator = "_"
        self._quote_symbol = "USDC"
        self._pair_suffix = ""

    @classmethod
    async def create(
        cls,
        message_bus: MessageBus,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> Self:
        """Create class instance and init_async."""
        instance = cls(message_bus, pass_guard, app_config)
        await instance.init_async()
        return instance

    async def init_async(self) -> None:
        """Initialize async shared attributes."""
        # Need to init fetcher first to get pair map
        self._fetcher = await OrderlyFetcher.create(
            self.account_id,
            self.private_key,
            self.message_bus,
        )

        self._trader = await OrderlyTrader.create(
            self._fetcher.pair_map,
            self.account_id,
            self.private_key,
        )

    @property
    def trader(self) -> OrderlyTrader:
        return self._trader

    @property
    def fetcher(self) -> OrderlyFetcher:
        return self._fetcher

    @property
    def available_pairs(self) -> set[str]:
        return set(self._fetcher.pair_map.values())

    @property
    def pair_map(self) -> dict[str, str]:
        return self._fetcher.pair_map

    @property
    def pair_prefix(self) -> str:
        return self._pair_prefix

    @property
    def pair_separator(self) -> str:
        return self._pair_separator

    @property
    def quote_symbol(self) -> str:
        return self._quote_symbol

    @property
    def pair_suffix(self) -> str:
        return self._pair_suffix

    @property
    def cached_prices(self) -> dict:
        return self.fetcher._cached_prices

    @property
    def account_info(self) -> dict[str, str]:
        return {
            "Exchange": self.name().capitalize(),
            "Exchange Type": self.exchange_type().name,
            "Account ID": self.account_id,
        }

    @property
    def stable_balance(self) -> Decimal:
        return self.fetcher._cached_stable_balance

    @property
    def min_leverage(self) -> int:
        return 1

    @property
    def max_leverage(self) -> int:
        return 20

    @asyncSlot()
    async def is_ready_to_trade(self) -> bool:
        return True

    @asyncSlot()
    async def approve_for_trading(self) -> None:
        pass

    @asyncSlot()
    async def create_order(
        self,
        pair: str,
        amount: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Decimal | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ) -> None:
        """Create new order."""
        if not self.is_valid_order_size(amount):
            msg = "Invalid order size"
            raise InvalidOrderSizeError(msg)

        symbol = self.fetcher.inverted_pair_map.get(pair)
        if not symbol:
            msg = f"Unknown pair {pair}"
            raise ValueError(msg)

        current_price = execution_price
        if current_price is None:
             # Fetch from cache
             if pair in self.cached_prices:
                 current_price = self.cached_prices[pair]["price"]
             else:
                 price_data = await self.fetcher.fetch_current_price(pair)
                 current_price = price_data["price"]

        if current_price == 0:
            msg = "Current price is 0, cannot calculate quantity"
            raise ValueError(msg)

        total_size_stable = amount * self.app_config.leverage
        quantity = total_size_stable / current_price

        # Round quantity to appropriate precision?
        # For now relying on API to handle excessive precision or rejecting it.

        side = "BUY" if trade_direction == PerpsTradeDirection.LONG else "SELL"
        o_type = "LIMIT" if trade_type == PerpsTradeType.LIMIT else "MARKET"

        args = {
            "symbol": symbol,
            "order_type": o_type,
            "side": side,
            "order_quantity": float(quantity),
            "reduce_only": False
        }

        if trade_type == PerpsTradeType.LIMIT:
             if execution_price is None:
                 msg = "Execution price required for limit order"
                 raise ValueError(msg)
             args["order_price"] = float(execution_price)

        try:
            res = await self.trader.create_order(args)
            self.message_bus.send_message.emit(UserMessage(
                f"Order created: {res.get('data', {}).get('order_id')}",
                level=MessageLevel.SUCCESS
            ))
        except TransactionFailedError as e:
            self.message_bus.send_message.emit(UserMessage(
                f"Order failed: {e}",
                level=MessageLevel.ERROR
            ))

    @asyncSlot()
    async def edit_order(
        self,
        order_data: OrderData,
        new_size_stable: Decimal,
        new_execution_price: Decimal,
    ) -> None:
        """Edit order."""
        quantity = new_size_stable / new_execution_price

        args = {
            "order_id": order_data["id"],
            "symbol": self.fetcher.inverted_pair_map[order_data["pair"]],
            "new_price": float(new_execution_price),
            "new_quantity": float(quantity)
        }

        try:
            await self.trader.edit_order(args)
            self.message_bus.send_message.emit(UserMessage(
                "Order edited",
                level=MessageLevel.SUCCESS
            ))
        except TransactionFailedError as e:
             self.message_bus.send_message.emit(UserMessage(
                f"Edit failed: {e}",
                level=MessageLevel.ERROR
            ))

    @asyncSlot()
    async def create_reduce_order(
        self,
        pair: str,
        size: Decimal,
        collateral_delta: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Decimal | None,
    ) -> None:
        """Create reduce order."""
        if execution_price is None and trade_type == PerpsTradeType.LIMIT:
             msg = "Price required for limit"
             raise ValueError(msg)

        price = execution_price
        if price is None:
             if pair in self.cached_prices:
                 price = self.cached_prices[pair]["price"]
             else:
                 price = (await self.fetcher.fetch_current_price(pair))["price"]

        quantity = size / price

        # trade_direction is the direction of the POSITION being reduced.
        order_side = "SELL" if trade_direction == PerpsTradeDirection.LONG else "BUY"

        o_type = "LIMIT" if trade_type == PerpsTradeType.LIMIT else "MARKET"

        symbol = self.fetcher.inverted_pair_map[pair]

        args = {
            "symbol": symbol,
            "order_type": o_type,
            "side": order_side,
            "order_quantity": float(quantity),
            "reduce_only": True
        }

        if trade_type == PerpsTradeType.LIMIT:
             args["order_price"] = float(price)

        try:
            res = await self.trader.create_order(args)
            self.message_bus.send_message.emit(UserMessage(
                f"Reduce order created: {res.get('data', {}).get('order_id')}",
                level=MessageLevel.SUCCESS
            ))
        except TransactionFailedError as e:
            self.message_bus.send_message.emit(UserMessage(
                f"Reduce failed: {e}",
                level=MessageLevel.ERROR
            ))

    @asyncSlot()
    async def close_position(self, perps_position: PerpsPosition) -> None:
        """Close position."""
        # Calculate quantity in base asset
        price = perps_position["open_price"]
        # Use cached price if available for better estimate of closing price for market order?
        if perps_position["pair"] in self.cached_prices:
            price = self.cached_prices[perps_position["pair"]]["price"]

        # position_size_stable is USD value.
        size_usd = perps_position["position_size_stable"]
        if price > 0:
            quantity = size_usd / price
        else:
            quantity = Decimal(0) # Should not happen if position is open

        trade_direction = perps_position["trade_direction"]
        order_side = "SELL" if trade_direction == PerpsTradeDirection.LONG else "BUY"

        symbol = self.fetcher.inverted_pair_map[perps_position["pair"]]

        args = {
            "symbol": symbol,
            "order_type": "MARKET",
            "side": order_side,
            "order_quantity": float(quantity),
            "reduce_only": True
        }

        try:
            res = await self.trader.create_order(args)
            self.message_bus.send_message.emit(UserMessage(
                f"Position closed: {res.get('data', {}).get('order_id')}",
                level=MessageLevel.SUCCESS
            ))
        except TransactionFailedError as e:
            self.message_bus.send_message.emit(UserMessage(
                f"Close failed: {e}",
                level=MessageLevel.ERROR
            ))

    @asyncSlot()
    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel order."""
        args = {
            "order_id": order_data["id"],
            "symbol": self.fetcher.inverted_pair_map[order_data["pair"]]
        }
        try:
            await self.trader.cancel_order(args)
            self.message_bus.send_message.emit(UserMessage(
                "Order cancelled",
                level=MessageLevel.SUCCESS
            ))
        except TransactionFailedError as e:
            self.message_bus.send_message.emit(UserMessage(
                f"Cancel failed: {e}",
                level=MessageLevel.ERROR
            ))

    @staticmethod
    def name() -> str:
        return "orderly"

    @staticmethod
    def new_account_info() -> NewAccountInfo:
        return NewAccountInfo(
            referral_link="https://orderly.network",
            secrets=["Orderly Account ID", "Orderly Private Key (Base58)"]
        )

    @staticmethod
    def exchange_type() -> ExchangeType:
        return ExchangeType.DEX

    @staticmethod
    def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
        if len(secrets) != 2:
            return False, "Need Account ID and Private Key"

        account_id, private_key = secrets
        if not account_id.startswith("0x"):
            pass

        import base58
        try:
            base58.b58decode(private_key)
        except Exception:
            return False, "Invalid Private Key (Base58)"

        return True, "Valid"
