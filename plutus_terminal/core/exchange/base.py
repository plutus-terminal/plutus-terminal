"""Base class for Exchange."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional, Protocol, Self

from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import (
    OptionsNotAvailableError,
    TransactionFailedError,
)
from plutus_terminal.core.types_ import (
    ExchangeType,
    NewAccountInfo,
    OptionsDirection,
    PerpsPosition,
    PerpsTradeType,
    PriceData,
    PriceHistory,
)
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from decimal import Decimal

    import pandas

    from plutus_terminal.core.exchange.types import OrderData, TradeResults
    from plutus_terminal.core.types_ import (
        PerpsTradeDirection,
    )

LOGGER = logging.getLogger(__name__)


class ExchangeFetcherMessageBus(QObject):
    """Message Bus for all fetch related events."""

    price_history_signal = Signal(PriceHistory)
    subscribed_prices_signal = Signal(dict)
    positions_signal = Signal(list)  # list[PerpsPosition]
    orders_signal = Signal(list)  # list[OrderData]
    price_synced = Signal(bool)


class ExchangeFetcher(Protocol):
    """Protocol for exchange fetch information."""

    async def fetch_price_history(
        self,
        pair: str,
        from_timestamp: int,
        resolution: str,
    ) -> PriceHistory:
        """Fetch the price history of pair for the given start and end time.

        Args:
            pair (str): Pair to fetch.
            from_timestamp (int): Timestamp for the leftmost bar.
            resolution (str): Bar resolution in seconds.

        Returns:
            PriceHistory: Dict with ohlcv.
        """
        ...

    async def subscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Subscribe to receive price updates for the given pair."""
        ...

    async def resubscribe_on_going_connections(self) -> None:
        """Resubscribe on going connections."""
        ...

    async def unsubscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Unsubscribe to receive price updates for the given pair."""
        ...

    async def receive_subscribed_prices(self) -> None:
        """Receive live data of subscribed prices from exchange."""
        ...

    async def watch_all_positions(self) -> None:
        """Watch all open positions."""
        ...

    async def fetch_all_positions(self) -> list[PerpsPosition]:
        """Fetch all open positions."""
        ...

    async def watch_all_orders(self) -> None:
        """Watch all open orders."""
        ...

    async def fetch_all_orders(self) -> list[OrderData]:
        """Fetch all open orders."""
        ...

    async def fetch_price_at_time(self, pair: str, timestamp: int) -> PriceData:
        """Fetch price at current time."""
        ...

    async def fetch_current_price(self, pair: str) -> PriceData:
        """Fetch current price of given pair."""
        ...

    def get_position_associated_with_order(self, order: OrderData) -> Optional[PerpsPosition]:
        """Get position associated with given order.

        Args:
            order (OrderData): Order to get position for.

        Returns:
            Optional[PerpsPosition]: Position associated with given order.
        """
        ...

    def get_position_fee(self, position_collateral: Decimal) -> Decimal:
        """Get fee for a given position.

        Args:
            position_collateral (Decimal): Position size to get fee for.

        Returns:
            Decimal: Fee amount in USD Stable Format.
        """
        ...

    def get_borrow_fee(self, perps_position: PerpsPosition) -> Decimal:
        """Get funding fee for a given position.

        Args:
            perps_position (PerpsPosition): Position to get funding fee for.

        Returns:
            Decimal: Funding fee in USD Stable Format.
        """
        ...

    def get_liquidation_price(self, perps_position: PerpsPosition) -> Decimal:
        """Get liquidation price for a given position.

        Args:
            perps_position (PerpsPosition): Position to get liquidation price for.

        Returns:
            Decimal: Liquidation price in USD Stable Format.
        """
        ...

    def get_pnl_percent(
        self,
        perps_position: PerpsPosition,
        current_price: Optional[Decimal],
    ) -> Decimal:
        """Get pnl percent for a given position.

        Args:
            perps_position (PerpsPosition): Position to get pnl for.
            current_price (Optional[Decimal]): Current price of the pair.

        Returns:
            Decimal: PNL in USD Stable Format.
        """
        ...

    async def stop(self) -> None:
        """Stop infinite loops and close connections."""
        ...


class ExchangeTrader(Protocol):
    """Protocol for exchange trading actions."""

    async def create_order(self, trade_arguments) -> TradeResults:  # noqa: ANN001
        """Create new order.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        ...

    async def create_reduce_order(self, trade_arguments) -> TradeResults:  # noqa: ANN001
        """Create new reduce only order.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Raises:
            NotImplementedError: If the trade direction is not supported.

        Returns:
            TradeResults: Result of the trade.
        """
        ...

    async def close_position(self, trade_arguments) -> TradeResults:  # noqa: ANN001
        """Close the give position.

        This are for positions that are already bought.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        ...

    async def cancel_order(self, trade_arguments) -> TradeResults:  # noqa: ANN001
        """Cancel the given order.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        ...

    async def edit_order(
        self,
        trade_arguments,  # noqa: ANN001
    ) -> TradeResults:
        """Update the given order.

        Args:
            trade_arguments (dict): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        ...


class ExchangeTraderDex(ExchangeTrader, Protocol):
    """Protocol for dex trading actions."""

    async def approve_contracts(self) -> None:
        """Approve necessary contracts for trading."""
        ...


class ExchangeOptions(Protocol):
    """Protocol for exchange options actions."""

    async def fetch_orders(self, options_orders_params) -> pandas.DataFrame:  # noqa: ANN001
        """Fetch options orders based on parameters.

        Args:
            options_orders_params (OrdersParams): Params for request.

        Returns:
            pandas.DataFrame: DataFrame with options orders.
        """
        ...

    async def buy_options(self, options_buy_params) -> None:  # noqa: ANN001
        """Buy options.

        Args:
            options_buy_params: Params to buy options.
        """
        ...

    def fetch_available_pairs(self) -> list[str]:
        """Fetch available pairs for options."""
        ...

    async def filter_with_strategy(
        self,
        direction: OptionsDirection,
        value: Decimal,
        pair: str,
    ) -> pandas.DataFrame:
        """Filter options based on strategy.

        Args:
            direction (OptionsDirection): Direction to buy the option.
            value (Decimal): Max value to spend.
            pair (str): Pair to open options for.

        Returns:
            pandas.DataFrame: DataFrame with options orders.
        """
        ...


class ExchangeBase(ABC):
    """Base class to interact with exchange."""

    def __init__(self, fetcher_bus: ExchangeFetcherMessageBus) -> None:
        """Initialize shared variables."""
        self.fetcher_bus = fetcher_bus
        self._is_price_synced = True
        self._watched_positions: list[PerpsPosition] = []
        self._async_tasks: list[asyncio.Task] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns: Exchange name."""

    @property
    @abstractmethod
    def trader(self) -> ExchangeTrader:
        """Returns: Exchange Trader."""

    @property
    @abstractmethod
    def fetcher(self) -> ExchangeFetcher:
        """Returns: Exchange Trader."""

    @property
    @abstractmethod
    def available_pairs(self) -> set:
        """Returns set with all available pairs."""

    @property
    @abstractmethod
    def pair_prefix(self) -> str:
        """Returns pair prefix."""

    @property
    @abstractmethod
    def pair_separator(self) -> str:
        """Returns pair separator."""

    @property
    @abstractmethod
    def quote_symbol(self) -> str:
        """Returns quote symbol."""

    @property
    @abstractmethod
    def pair_suffix(self) -> str:
        """Returns pair suffix."""

    @property
    @abstractmethod
    def cached_prices(self) -> dict:
        """Return all prices cache."""

    @classmethod
    @abstractmethod
    async def create(cls, fetcher_bus: ExchangeFetcherMessageBus) -> Self:
        """Create class instance and init_async."""

    @property
    def default_pair(self) -> str:
        """Return default pair name to auto subscribe."""
        return self.format_pair_from_coin("BTC")

    @property
    def options(self) -> ExchangeOptions:
        """Returns: Exchange Options."""
        raise OptionsNotAvailableError

    def has_options(self) -> bool:
        """Return if exchange has options."""
        try:
            return self.options is not None
        except OptionsNotAvailableError:
            return False

    def format_pair_from_coin(self, coin: str) -> str:
        """Format coin to pair name."""
        return f"{self.pair_prefix}{coin}{self.pair_separator}{self.quote_symbol}{self.pair_suffix}"

    def format_simple_pair_from_pair(self, pair: str) -> str:
        """Format pair name to simple pair."""
        simple_pair = ""
        if self.pair_prefix:
            simple_pair = pair[len(self.pair_prefix) :]

        if self.pair_suffix:
            simple_pair = simple_pair[: -len(self.pair_suffix)]
        return simple_pair

    def format_coin_from_pair(self, pair: str) -> str:
        """Format pair name to coin."""
        simple_pair = self.format_simple_pair_from_pair(pair)
        return simple_pair.split(self.pair_separator)[0]

    async def fetch_prices(self) -> None:
        """Fetch prices in an infinite loop."""
        await self.fetcher.subscribe_to_price(self.default_pair)
        self._async_tasks.append(
            asyncio.create_task(self.fetcher.receive_subscribed_prices()),
        )
        self._async_tasks.append(
            asyncio.create_task(self.fetcher.watch_all_positions()),
        )
        self._async_tasks.append(asyncio.create_task(self.fetcher.watch_all_orders()))
        self.fetcher_bus.positions_signal.connect(self._update_watched_positions)

    @asyncSlot()
    async def _update_watched_positions(
        self,
        all_positions: list[PerpsPosition],
    ) -> None:
        """Update list of current watched positions.

        Subscribe or remove subscriptions based on new positions.
        """
        if all_positions != self._watched_positions:
            to_subscribe = [
                position["pair"]
                for position in all_positions
                if position not in self._watched_positions
            ]
            to_unsubscribe = [
                position["pair"]
                for position in self._watched_positions
                if position not in all_positions
            ]
            for pair in to_subscribe:
                await self.fetcher.subscribe_to_price(pair)

            for pair in to_unsubscribe:
                await self.fetcher.unsubscribe_to_price(pair)

            self._watched_positions = all_positions

    async def fetch_price_history(
        self,
        pair: str,
        resolution: str,
        bars_num: int = 200,
    ) -> PriceHistory:
        """Fetch current price history for current pair.

        Args:
            pair (str): Pair to fetch.
            resolution (str): Bar resolution.
            bars_num (int): Number of bars expected for resolution.
        """
        now_timestamp = int(time.time())
        match resolution:
            case "5":
                start_timestamp = now_timestamp - 5 * 60 * bars_num
            case "15":
                start_timestamp = now_timestamp - 15 * 60 * bars_num
            case "30":
                start_timestamp = now_timestamp - 30 * 60 * bars_num
            case "60":
                start_timestamp = now_timestamp - 60 * 60 * bars_num
            case "240":
                start_timestamp = now_timestamp - 240 * 60 * bars_num
            case _:
                start_timestamp = now_timestamp - bars_num * 60

        return await self.fetcher.fetch_price_history(
            pair=pair,
            from_timestamp=start_timestamp,
            resolution=resolution,
        )

    @asyncSlot()
    async def set_all_leverage(self, leverage: int) -> None:
        """Set leverage for all positions.

        Args:
            leverage (int): Leverage to set.
        """
        Toast.show_message(
            f"Leverage set to all pairs: {leverage}x",
            type_=ToastType.SUCCESS,
        )
        CONFIG.leverage = leverage

    @asyncSlot()
    async def set_leverage(self, coin: str, leverage: int) -> None:
        """Set leverage for pair.

        Args:
            coin (str): Coin to set leverage for.
            leverage (int): Leverage to set.
        """
        pair = self.format_pair_from_coin(coin)
        Toast.show_message(
            f"Leverage of {pair} set to: {leverage}x",
            type_=ToastType.SUCCESS,
        )
        CONFIG.leverage = leverage

    @abstractmethod
    async def create_order(
        self,
        pair: str,
        amount: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> None:
        """Create new order.

        Args:
            pair (str): Pair to open trade for.
            amount (Decimal): Value in stable to open trade for, this will be multiplied
                by de configured leverage.
            trade_direction (TradeDirection): Trade direction.
            trade_type (TradeType): Trade type.
            execution_price (Optional[Decimal], optional): Execution price.
            take_profit (Optional[float], optional): Take profit price.
                If None use CONFIG.take_profit.
            stop_loss (Optional[float], optional): Stop loss price.
                If None use CONFIG.stop_loss.
        """

    @abstractmethod
    async def edit_order(
        self,
        order_data: OrderData,
        new_size_stable: Decimal,
        execution_price: Optional[Decimal],
    ) -> None:
        """Edit existent order.

        Args:
            order_data (OrderData): Order to edit.
            new_size_stable (Decimal): Value in stable to open trade for, this will be multiplied
                by de configured leverage.
            execution_price (Optional[Decimal], optional): Execution price.
        """
        ...

    @abstractmethod
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
            size (Decimal): Value in stable to open trade for, this will be multiplied
                by de configured leverage.
            trade_direction (TradeDirection): Trade direction.
            trade_type (TradeType): Trade type.
            execution_price (Decimal): Execution price.
            is_stop_loss (bool): True if this is a stop loss order.
                False if it's a take profit.
        """

    @abstractmethod
    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel the given order.

        Args:
            order_data (OrderData): Order to close.

        Raises:
            TransactionFailed: If the transaction fails.
        """
        ...

    @asyncSlot()
    async def close_position(self, perps_position: PerpsPosition) -> None:
        """Close position for pair.

        Close position and emit positions signal.

        Args:
            perps_position (PerpsPosition): Position to close.
        """
        toast_id = Toast.show_message(
            f"Closing position for {perps_position['pair']}",
            type_=ToastType.WARNING,
        )
        try:
            await self.trader.close_position(perps_position)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to close position > {error}",
                type_=ToastType.ERROR,
            )
        all_positions = await self.fetcher.fetch_all_positions()
        self.fetcher_bus.positions_signal.emit(all_positions)
        Toast.update_message(toast_id, "Position closed", type_=ToastType.SUCCESS)

    def get_position_associated_with_order(self, order: OrderData) -> Optional[PerpsPosition]:
        """Get position associated with given order.

        Args:
            order (OrderData): Order to get position for.

        Returns:
            Optional[PerpsPosition]: Position associated with given order.
        """
        return self.fetcher.get_position_associated_with_order(order)

    def get_position_fee(self, position_collateral: Decimal) -> Decimal:
        """Get fee for a given position.

        Args:
            position_collateral (Decimal): Position size to get fee for.

        Returns:
            Decimal: Position fee.
        """
        return self.fetcher.get_position_fee(position_collateral)

    def get_borrow_fee(self, perps_position: PerpsPosition) -> Decimal:
        """Get funding fee for a given position.

        Args:
            perps_position (PerpsPosition): Position to get funding fee for.

        Returns:
            Decimal: Funding fee in USD Stable Format.
        """
        return self.fetcher.get_borrow_fee(perps_position)

    def get_liquidation_price(self, perps_position: PerpsPosition) -> Decimal:
        """Get liquidation price for a given position.

        Args:
            perps_position (PerpsPosition): Position to get liquidation price for.

        Returns:
            Decimal: Liquidation price in USD Stable Format.
        """
        return self.fetcher.get_liquidation_price(perps_position)

    def get_pnl_percent(
        self,
        perps_position: PerpsPosition,
        current_price: Optional[Decimal],
    ) -> Decimal:
        """Get pnl percent for a given position.

        Args:
            perps_position (PerpsPosition): Position to get pnl for.
            current_price (Optional[Decimal]): Current price of the pair.

        Returns:
            Decimal: PNL in USD Stable Format.
        """
        return self.fetcher.get_pnl_percent(perps_position, current_price)

    async def buy_options_with_strategy(
        self,
        direction: OptionsDirection,  # noqa: ARG002
        value: Decimal,  # noqa: ARG002
        pair: str,  # noqa: ARG002
    ) -> None:
        """Buy options based on strategy.

        Args:
            direction (OptionsDirection): Direction to buy the option.
            value (Decimal): Max value in stable to spend.
            pair (str): Pair to open options for.
        """
        raise OptionsNotAvailableError

    async def stop(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        LOGGER.info("Stopping exchange %s loops", self.name)
        await self.fetcher.stop()

    @staticmethod
    @abstractmethod
    def new_account_info() -> NewAccountInfo:
        """Provide info for new account creation."""

    @staticmethod
    @abstractmethod
    def exchange_type() -> ExchangeType:
        """Return exchange type."""

    @staticmethod
    @abstractmethod
    def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
        """Validate secrets."""
