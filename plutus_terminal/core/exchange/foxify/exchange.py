"""Foxify Exchange."""

from __future__ import annotations

import asyncio
from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Self

import orjson
from qasync import asyncSlot
from web3 import Account
from web3.types import Gwei

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import (
    InvalidOrderSizeError,
    TransactionFailedError,
)
from plutus_terminal.core.exchange import helpers as exchange_helpers
from plutus_terminal.core.exchange.base import (
    ExchangeBase,
)
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.foxify.fetcher import FoxifyFetcher
from plutus_terminal.core.exchange.foxify.trader import FoxifyTrader
from plutus_terminal.core.exchange.web3 import web3_utils
from plutus_terminal.core.exchange.web3.cycle_provider import build_cycle_provider
from plutus_terminal.core.types_ import (
    ExchangeType,
    NewAccountInfo,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from eth_account.signers.local import LocalAccount

    from plutus_terminal.core.exchange.base import (
        ExchangeFetcherMessageBus,
    )
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
    from plutus_terminal.core.password_guard import PasswordGuard


LOGGER = logging.getLogger(__name__)


class FoxifyExchange(ExchangeBase):
    """Class to interact with Foxify Exchange."""

    def __init__(self, fetcher_bus: ExchangeFetcherMessageBus, pass_guard: PasswordGuard) -> None:
        """Initialize shared attributes.

        Args:
            fetcher_bus (ExchangeFetcherMessageBus): ExchangeFetcherMessageBus.
            pass_guard (PasswordGuard): PasswordGuard.
        """
        super().__init__(fetcher_bus=fetcher_bus, pass_guard=pass_guard)
        self.web3_provider = build_cycle_provider("Arbitrum One Trader")
        # Get current account
        keyring_account = CONFIG.current_keyring_account
        decrypted_password = self._pass_guard.get_keyring_password(keyring_account)
        web3_account: LocalAccount = Account.from_key(orjson.loads(decrypted_password)[0])

        self.web3_account = web3_account
        self._pair_prefix = "Crypto."
        self._pair_separator = "/"
        self._quote_symbol = "USD"
        self._pair_suffix = ""
        self._pair_map = self.build_pair_map()
        self._inverted_pair_map = {v: k for k, v in self._pair_map.items()}

    @classmethod
    async def create(
        cls,
        fetcher_bus: ExchangeFetcherMessageBus,
        pass_guard: PasswordGuard,
    ) -> Self:
        """Create class instance and init_async.

        Args:
            fetcher_bus (ExchangeFetcherMessageBus): ExchangeFetcherMessageBus.
            pass_guard (PasswordGuard): PasswordGuard.

        Returns:
            FoxifyExchange: Instance of FoxifyExchange.
        """
        instance = cls(fetcher_bus, pass_guard)
        await instance.init_async()
        return instance

    async def init_async(self) -> None:
        """Initialize async shared attributes."""
        self._trader = await FoxifyTrader.create(
            self._pair_map,
            self.web3_account,
            Gwei(0),
        )
        self._fetcher = await FoxifyFetcher.create(
            self._pair_map,
            self.web3_account.address,
            self.fetcher_bus,
        )
        # Options are being rebuild in Foxify. Disable for now
        # self._options = await FoxifyOptions.create(self.web3_account, Gwei(0))

    @property
    def trader(self) -> FoxifyTrader:
        """Returns: Exchange Trader."""
        return self._trader

    @property
    def fetcher(self) -> FoxifyFetcher:
        """Returns: Exchange Trader."""
        return self._fetcher

    @property
    def available_pairs(self) -> set:
        """Returns set with all available pairs."""
        return set(self._pair_map.values())

    @property
    def pair_map(self) -> dict[str, str]:
        """Returns pair map."""
        return self._pair_map

    @property
    def pair_prefix(self) -> str:
        """Returns pair prefix if any."""
        return self._pair_prefix

    @property
    def pair_separator(self) -> str:
        """Returns the pair separator if any."""
        return self._pair_separator

    @property
    def quote_symbol(self) -> str:
        """Return quote symbol."""
        return self._quote_symbol

    @property
    def pair_suffix(self) -> str:
        """Returns pair suffix."""
        return self._pair_suffix

    @property
    def cached_prices(self) -> dict:
        """Return all prices from cache."""
        return self.fetcher._cached_prices  # noqa: SLF001

    @property
    def account_info(self) -> dict[str, str]:
        """Return info to be added to account info widget."""
        return {
            "Exchange": self.name().capitalize(),
            "Exchange Type": self.exchange_type().name,
            "Wallet": f"{self.web3_account.address[:5]}...{self.web3_account.address[-5:]}",
        }

    @property
    def stable_balance(self) -> Decimal:
        """Return stable balance."""
        return self.fetcher._cached_stable_balance  # noqa: SLF001

    @property
    def min_order_size(self) -> Decimal:
        """Return min trade size."""
        # Could not find this from any contracts only on the front end.
        # TODO: Fix this with the value from the contract
        return Decimal(10)

    # @property
    # def options(self) -> ExchangeOptions:
    #     """Return exchange options."""
    #     return self._options

    @asyncSlot()
    async def is_ready_to_trade(self) -> bool:
        """Check if contracts are approaved.

        Returns:
            bool: True if account is ready to trade.
        """
        router_approved, pos_router_plugin, order_book_plugin = await asyncio.gather(
            foxify_utils.is_stable_approved(
                self.web3_provider,
                self.web3_provider.to_checksum_address(foxify_utils.FOXIFY_ROUTER),
                self.web3_account.address,
            ),
            foxify_utils.is_plugin_approved(
                self.web3_provider,
                foxify_utils.FOXIFY_POSITION_ROUTER,
                self.web3_account.address,
            ),
            foxify_utils.is_plugin_approved(
                self.web3_provider,
                foxify_utils.FOXIFY_ORDER_BOOK,
                self.web3_account.address,
            ),
        )
        return all([router_approved, pos_router_plugin, order_book_plugin])

    @asyncSlot()
    async def approve_for_trading(self) -> None:
        """Approve contracts needed for trading."""
        await foxify_utils.approve_stable(
            self.web3_provider,
            foxify_utils.FOXIFY_ROUTER,
            self.web3_account,
        )
        await foxify_utils.approve_plugin(
            self.web3_provider,
            foxify_utils.FOXIFY_POSITION_ROUTER,
            self.web3_account,
        )
        await foxify_utils.approve_plugin(
            self.web3_provider,
            foxify_utils.FOXIFY_ORDER_BOOK,
            self.web3_account,
        )
        await foxify_utils.ensure_referral(self.web3_provider, self.web3_account)

    async def fetch_prices(self) -> None:
        """Fetch prices in an infinite loop."""
        await self.fetcher.websocket_connect()
        await super().fetch_prices()
        self._async_tasks.append(
            asyncio.create_task(self.fetcher.fetch_positions_funding_rates()),
        )

    def build_pair_map(self) -> dict[str, str]:
        """Build pair map based on foxify pairs.

        Returns:
            dict[str, str]: Pair map.
        """
        with Path.open(Path(__file__).parent.joinpath("pair_map.json")) as f:
            pair_map = json.load(f)

        for pair in pair_map:
            pair_map[pair] = self.format_pair_from_coin(pair_map[pair])

        return pair_map

    @asyncSlot()
    async def create_order(
        self,
        pair: str,
        amount: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal] = None,
        take_profit_percent: Optional[float] = None,
        stop_loss_percent: Optional[float] = None,
    ) -> None:
        """Create new order.

        Args:
            pair (str):  Pair to open trade for.
            amount (Decimal): Value in stable to open trade for, this will be multiplied
                by de configured leverage.
            trade_direction (TradeDirection): Trade direction.
            trade_type (TradeType): Trade type.
            execution_price (Optional[Decimal], optional): Execution price.
                If None use current price.
            take_profit_percent (Optional[float], optional): Take profit price.
                If None use CONFIG.take_profit.
            stop_loss_percent (Optional[float], optional): Stop loss price.
                If None use CONFIG.stop_loss.

        Raises:
            InvalidOrderSizeError: If order size is not valid.
            TransactionFailedError: If transaction failed
        """
        if not self.is_valid_order_size(amount):
            msg = (
                f"Invalid order size. Order needs to be: "
                f"less than {self.min_order_size:.2f} and greater than {self.max_order_size:.2f}"
            )
            raise InvalidOrderSizeError(msg)

        toast_id = Toast.show_message(
            f"Creating {trade_type.name} order for {pair}",
            type_=ToastType.WARNING,
        )

        # Get cached price if available otherwise fetch it.
        if execution_price is None and trade_type == PerpsTradeType.MARKET:
            try:
                execution_price = Decimal(self.cached_prices[pair]["price"])
            except KeyError:
                current_price_data = await self.fetcher.fetch_current_price(pair)
                execution_price = Decimal(current_price_data["price"])

            if trade_direction == PerpsTradeDirection.LONG:
                execution_price += execution_price * Decimal(foxify_utils.MAX_SLIPPAGE)
            else:
                execution_price -= execution_price * Decimal(foxify_utils.MAX_SLIPPAGE)
        elif not isinstance(execution_price, Decimal):
            msg = "Invalid execution price."
            raise TypeError(msg)

        acceptable_price = execution_price
        take_profit_execution = exchange_helpers.get_take_profit_target(
            execution_price,
            take_profit_percent,
            trade_direction,
        )
        stop_loss_execution = exchange_helpers.get_stop_loss_target(
            execution_price,
            stop_loss_percent,
            trade_direction,
        )

        size_delta = amount * CONFIG.leverage

        trade_args = foxify_utils.OpenTradingArgs(
            {
                "index_token": self._inverted_pair_map[pair],
                "amount_in": amount,
                "size_delta": size_delta,
                "trade_direction": trade_direction,
                "acceptable_price": acceptable_price,
                "trade_type": trade_type,
                "stop_loss": stop_loss_execution,
                "take_profit": take_profit_execution,
            },
        )
        try:
            trade_result = await self.trader.create_order(trade_args)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to create order: {error}",
                type_=ToastType.ERROR,
            )
            return

        if isinstance(trade_result, dict):
            msg = "Unexpected error when creating order."
            raise TransactionFailedError(msg)

        await web3_utils.await_receipt_and_report(
            trade_result,
            self.web3_provider,
            "Order Created.",
            "https://arbiscan.io/tx/",
            LOGGER,
            toast_id,
        )

    @asyncSlot()
    async def edit_order(
        self,
        order_data: OrderData,
        new_size_stable: Decimal,
        new_execution_price: Decimal,
    ) -> None:
        """Edit existent order.

        Args:
            order_data (OrderData): Order to edit.
            new_size_stable (Decimal): Value in stable to open trade for, this will be multiplied
                by de configured leverage.
            new_execution_price (Decimal, optional): Execution price.

        Raises:
            TransactionFailedError: If transaction failed
        """
        toast_id = Toast.show_message(
            f"Editing order {order_data['id']}",
            type_=ToastType.WARNING,
        )

        if new_size_stable > order_data["size_stable"]:
            msg = "New size must be smaller/equal than current size."
            raise ValueError(msg)

        order_extra = order_data.get("extra", None)
        if order_extra is None:
            msg = "Missing 'extra' attribute in order_data."
            raise AttributeError(msg)
        order_index = order_extra.get("index", None)
        if order_index is None:
            msg = "Missing 'index' attribute in order_extra."
            raise AttributeError(msg)
        order_trigger_above_threshold = order_extra.get("trigger_above_threshold", None)
        if order_trigger_above_threshold is None:
            msg = "Missing 'trigger_above_threshold' attribute in order_extra."
            raise AttributeError(msg)

        edit_args = foxify_utils.EditOrderArgs(
            {
                "order_index": order_index,
                "size_delta": new_size_stable,
                "acceptable_price": new_execution_price,
                "trigger_above_threshold": order_trigger_above_threshold,
                "trade_type": order_data["order_type"],
            },
        )

        try:
            trade_result = await self.trader.edit_order(edit_args)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to edit order: {error}",
                type_=ToastType.ERROR,
            )
            return
        if isinstance(trade_result, dict):
            msg = "Unexpected error when creating order."
            raise TransactionFailedError(msg)

        await web3_utils.await_receipt_and_report(
            trade_result,
            self.web3_provider,
            "Order Edited.",
            "https://arbiscan.io/tx/",
            LOGGER,
            toast_id,
        )

    @asyncSlot()
    async def create_reduce_order(
        self,
        pair: str,
        size: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal],
    ) -> None:
        """Create new reduce only order.

        Args:
            pair (str):  Pair to open trade for.
            size (Decimal): Value in stable to reduce trade for.
            trade_direction (TradeDirection): Trade direction.
            trade_type (TradeType): Trade type.
            execution_price (Decimal): Execution price.

        Raises:
            TransactionFailedError: If transaction failed
        """
        toast_id = Toast.show_message(
            f"Creating {trade_type.name} order for {pair}",
            type_=ToastType.WARNING,
        )

        # Get cached price if available otherwise fetch it.
        if execution_price is None and trade_type == PerpsTradeType.MARKET:
            try:
                execution_price = Decimal(self.cached_prices[pair]["price"])
            except KeyError:
                current_price_data = await self.fetcher.fetch_current_price(pair)
                execution_price = Decimal(current_price_data["price"])
            if trade_direction == PerpsTradeDirection.LONG:
                execution_price = execution_price + execution_price * Decimal(
                    foxify_utils.MAX_SLIPPAGE,
                )
            else:
                execution_price = execution_price - execution_price * Decimal(
                    foxify_utils.MAX_SLIPPAGE,
                )
        elif not isinstance(execution_price, Decimal):
            msg = "Invalid execution price."
            raise TypeError(msg)

        acceptable_price = execution_price
        trade_args = foxify_utils.ReduceTradingArgs(
            {
                "index_token": self._inverted_pair_map[pair],
                "size_delta": size,
                "trade_direction": trade_direction,
                "acceptable_price": acceptable_price,
                "trade_type": trade_type,
            },
        )

        try:
            trade_result = await self.trader.create_reduce_order(trade_args)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to create reduce order: {error}",
                type_=ToastType.ERROR,
            )
            return
        except NotImplementedError as error:
            Toast.update_message(
                toast_id,
                f"Reduce order not supported: {error}",
                type_=ToastType.ERROR,
            )
            return

        if isinstance(trade_result, dict):
            msg = "Unexpected error when creating reduce order."
            raise TransactionFailedError(msg)

        await web3_utils.await_receipt_and_report(
            trade_result,
            self.web3_provider,
            "Reduce Order Created.",
            "https://arbiscan.io/tx/",
            LOGGER,
            toast_id,
        )

    @asyncSlot()
    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel the given order.

        Args:
            order_data  (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.
        """
        toast_id = Toast.show_message(
            f"Canceling {order_data['order_type'].name} order for {order_data['pair']}",
            type_=ToastType.WARNING,
        )

        order_extra = order_data.get("extra", None)
        if order_extra is None:
            msg = "Missing 'extra' attribute in order_data."
            raise AttributeError(msg)
        order_index = order_extra.get("index", None)
        if order_index is None:
            msg = "Missing 'index' attribute in order_extra."
            raise AttributeError(msg)

        cancel_args = foxify_utils.CancelOrderArgs(
            {
                "order_index": int(order_index),
                "reduce_only": order_data["reduce_only"],
            },
        )

        try:
            trade_result = await self.trader.cancel_order(cancel_args)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to create reduce order: {error}",
                type_=ToastType.ERROR,
            )
            return

        if isinstance(trade_result, dict):
            msg = "Unexpected error when canceling order."
            raise TransactionFailedError(msg)

        await web3_utils.await_receipt_and_report(
            trade_result,
            self.web3_provider,
            "Order Cancelled.",
            "https://arbiscan.io/tx/",
            LOGGER,
            toast_id,
        )

    @asyncSlot()
    async def close_position(self, perp_position: PerpsPosition) -> None:
        """Close position for pair.

        Args:
            perp_position (PerpPosition): Position to close.

        Raises:
            TransactionFailed: If the transaction fails.
        """
        toast_id = Toast.show_message(
            f"Closing position for {perp_position['pair']}",
            type_=ToastType.WARNING,
        )

        # Get cached price if available otherwise fetch it.
        try:
            current_price = Decimal(self.cached_prices[perp_position["pair"]]["price"])
        except KeyError:
            current_price_data = await self.fetcher.fetch_current_price(
                perp_position["pair"],
            )
            current_price = Decimal(current_price_data["price"])

        # Calculate execution price with slippage
        if perp_position["trade_direction"] == PerpsTradeDirection.LONG:
            acceptable_price = current_price - current_price * Decimal(
                foxify_utils.MAX_SLIPPAGE,
            )
        else:
            acceptable_price = current_price + current_price * Decimal(
                foxify_utils.MAX_SLIPPAGE,
            )

        trade_arguments = foxify_utils.CloseTradingArgs(
            {
                "index_token": self._inverted_pair_map[perp_position["pair"]],
                "size_delta": Decimal(perp_position["position_size_stable"]),
                "trade_direction": perp_position["trade_direction"],
                "acceptable_price": acceptable_price,
            },
        )
        try:
            trade_result = await self.trader.close_position(trade_arguments)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to close position: {error}",
                type_=ToastType.ERROR,
            )
            return

        if isinstance(trade_result, dict):
            msg = "Unexpected error when closing position."
            raise TransactionFailedError(msg)

        await web3_utils.await_receipt_and_report(
            trade_result,
            self.web3_provider,
            "Position Closed.",
            "https://arbiscan.io/tx/",
            LOGGER,
            toast_id,
        )

    # @asyncSlot()
    # async def buy_options_with_strategy(
    #     self, direction: OptionsDirection, value: Decimal, pair: str
    # ) -> None:
    #     """Buy options based on strategy.
    #
    #     Args:
    #         direction (OptionsDirection): Direction to buy the option.
    #         value (Decimal): Max value in stable to spend.
    #         pair (str): Pair to open options for.
    #     """
    #     extracted_data = await self.options.filter_with_strategy(direction, value, pair)
    #     if extracted_data.empty:
    #         Toast.show_message(
    #             "No options avaialble for the given strategy.",
    #             type_=ToastType.ERROR,
    #         )
    #         return
    #
    #     # Store orders ids and amount to buy for each order.
    #     orders_to_buy: OptionsBuyParams = {"orders": {}, "price_id": ""}
    #     available_to_spend = int(value.scaleb(6))
    #
    #     # Set price_id using the first valid oracle priceId
    #     if not orders_to_buy["price_id"]:
    #         orders_to_buy["price_id"] = extracted_data["oracle"].iloc[0]["priceId"]
    #
    #     # Calculate order amounts
    #     for _, row in extracted_data[["orderId", "available"]].iterrows():
    #         if available_to_spend >= row["available"]:
    #             orders_to_buy["orders"][row["orderId"]] = row["available"]
    #         else:
    #             orders_to_buy["orders"][row["orderId"]] = available_to_spend
    #             break
    #         available_to_spend -= orders_to_buy["orders"][row["orderId"]]
    #
    #     await self._options.buy_options(orders_to_buy)

    @staticmethod
    def name() -> str:
        """Return exchange name."""
        return "foxify"

    @staticmethod
    def new_account_info() -> NewAccountInfo:
        """Provide info for new account creation."""
        return NewAccountInfo(
            referral_link="https://perp.foxify.trade/#/trade/?ref=plutus_terminal",
            secrets=["Private Key"],
        )

    @staticmethod
    def exchange_type() -> ExchangeType:
        """Return exchange type."""
        return ExchangeType.DEX

    @staticmethod
    def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
        """Validate private key."""
        try:
            Account.from_key(secrets[0])
        except ValueError:
            return False, "Private key is invalid."
        else:
            return True, "Valid private key."
