"""Controller for TradingChart."""

from __future__ import annotations

from typing import TYPE_CHECKING
import logging
import pandas
from qasync import asyncSlot
from PySide6.QtCore import QObject, Signal

from plutus_terminal.ui import ui_utils

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition

LOGGER = logging.getLogger(__name__)

class TradingChartController(QObject):
    """Controller for TradingChart."""

    update_chart_data = Signal(pandas.DataFrame) # start data
    append_chart_data = Signal(pandas.DataFrame) # appended data
    update_tick = Signal(pandas.Series)
    update_price_label = Signal(str)
    draw_positions_signal = Signal(list) # list[PerpsPosition]
    draw_orders_signal = Signal(list) # list[OrderData]
    update_pair_text = Signal(str)

    def __init__(self, ui_controller: UIController) -> None:
        """Initialize controller.

        Args:
            ui_controller (UIController): UI Controller.
        """
        super().__init__()
        self.ui_controller = ui_controller
        self.current_timeframe = "1" # Should match UIController default or sync with it.
        # Actually UIController has current_timeframe.

        self.connect_signals()

    def connect_signals(self) -> None:
        """Connect signals."""
        self.ui_controller.message_bus.subscribed_prices_fetched.connect(self.on_prices_fetched)
        self.ui_controller.message_bus.positions_fetched.connect(self.on_positions_fetched)
        self.ui_controller.message_bus.orders_fetched.connect(self.on_orders_fetched)

        self.ui_controller.pair_changed.connect(self.on_pair_changed)
        self.ui_controller.exchange_changed.connect(self.on_exchange_changed)
        self.ui_controller.timeframe_changed.connect(self.on_timeframe_changed)

    @property
    def current_pair(self) -> str:
        """Get current pair.

        Returns:
            str: Current pair.
        """
        return self.ui_controller.current_pair

    @asyncSlot()
    async def on_pair_changed(self, pair: str) -> None:
        """Handle pair change.

        Args:
            pair (str): Pair.
        """
        self.ui_controller.message_bus.blockSignals(True)
        history_dataframe, _ = await self.ui_controller.fetch_price_history()
        self.update_chart_data.emit(history_dataframe)
        self.ui_controller.message_bus.blockSignals(False)

        pair_text = self.ui_controller.format_simple_pair_from_pair(pair)
        self.update_pair_text.emit(pair_text)

    @asyncSlot()
    async def on_timeframe_changed(self, timeframe_value: str) -> None:
        """Handle timeframe change.

        Args:
            timeframe_value (str): Timeframe value.
        """
        self.current_timeframe = timeframe_value
        history_dataframe = await self.ui_controller.fetch_price_history_for_timeframe(timeframe_value)
        self.update_chart_data.emit(history_dataframe)

    @asyncSlot()
    async def on_exchange_changed(self) -> None:
        """Handle exchange change."""
        await self.ui_controller.change_timeframe(self.ui_controller.current_timeframe)

    def on_prices_fetched(self, data: dict) -> None:
        """Handle price update.

        Args:
            data (dict): Price data.
        """
        try:
            price = data[self.ui_controller.current_pair]
        except KeyError:
            return

        tick = pandas.Series(price)
        tick["price"] = float(tick["price"])
        tick["date"] = ui_utils.convert_timestamp_to_local_timezone(tick["date"])

        self.update_tick.emit(tick)

        minimal_digits = ui_utils.get_minimal_digits(tick["price"], 4)
        self.update_price_label.emit(f"${tick['price']:,.{minimal_digits}f}")

    def on_positions_fetched(self, positions: list[PerpsPosition]) -> None:
        """Handle positions update.

        Args:
            positions (list[PerpsPosition]): Positions.
        """
        self.draw_positions_signal.emit(positions)

    def on_orders_fetched(self, orders: list[OrderData]) -> None:
        """Handle orders update.

        Args:
            orders (list[OrderData]): Orders.
        """
        self.draw_orders_signal.emit(orders)

    async def fetch_more_data(self, to_timestamp: int) -> None:
        """Fetch more historical data.

        Args:
            to_timestamp (int): Timestamp to fetch to.
        """
        history = await self.ui_controller.current_exchange.fetch_price_history(
            self.ui_controller.current_pair,
            self.ui_controller.current_timeframe,
            bars_num=ui_utils.DEFAULT_BAR_NUMBERS * 3,
            to_timestamp=to_timestamp,
        )
        self.append_chart_data.emit(pandas.DataFrame(history))

    async def change_timeframe_request(self, timeframe_value: str) -> None:
        """Request to change timeframe (from UI).

        Args:
            timeframe_value (str): Timeframe value.
        """
        await self.ui_controller.change_timeframe(timeframe_value)

    def change_pair_request(self, pair: str) -> None:
        """Request to change pair.

        Args:
            pair (str): Pair.
        """
        asyncSlot(self.ui_controller.change_current_pair)(pair)
