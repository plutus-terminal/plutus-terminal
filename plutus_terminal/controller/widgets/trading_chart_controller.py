"""Controller for trading-chart widget orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING
import weakref

import pandas
from PySide6.QtCore import QObject
from qasync import asyncSlot

from plutus_terminal.controller.widgets.ui_update_batcher import UiUpdateBatcher
from plutus_terminal.ui import ui_utils

if TYPE_CHECKING:
    from lightweight_charts import Chart

    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
    from plutus_terminal.ui.widgets.trading_chart import TradingChart


class TradingChartController(QObject):
    """Coordinate async chart data loading and event subscriptions."""

    def __init__(self, ui_controller: UIController, view: TradingChart) -> None:
        """Initialize controller with the owning chart widget."""
        super().__init__(parent=view)
        self._ui_controller = ui_controller
        self._view_ref: weakref.ReferenceType[TradingChart] = weakref.ref(view)
        self._ui_batcher = UiUpdateBatcher.shared()
        self._connect_signals()

    def _view(self) -> TradingChart | None:
        """Return the live view instance when available."""
        return self._view_ref()

    def _connect_signals(self) -> None:
        """Connect external app signals to chart rendering callbacks."""
        self._ui_controller.message_bus.subscribed_prices_fetched.connect(self.handle_price_tick)
        self._ui_controller.message_bus.positions_fetched.connect(self.handle_positions_fetched)
        self._ui_controller.message_bus.orders_fetched.connect(self.handle_orders_fetched)

        self._ui_controller.pair_changed.connect(self.handle_pair_changed)
        self._ui_controller.exchange_changed.connect(self.handle_exchange_changed)
        self._ui_controller.timeframe_changed.connect(self.handle_timeframe_changed)

    def handle_price_tick(self, data: dict) -> None:
        """Update the live price label and chart candle from price ticks."""
        view = self._view()
        if view is None:
            return
        try:
            price = data[self._ui_controller.current_pair]
        except KeyError:
            return

        tick = pandas.Series(price)
        tick["price"] = float(tick["price"])
        tick["date"] = ui_utils.convert_timestamp_to_local_timezone(tick["date"])
        minimal_digits = ui_utils.get_minimal_digits(tick["price"], 4)
        self._ui_batcher.submit(
            f"trading-chart-tick:{id(view)}",
            lambda: self._apply_price_tick(view, tick, minimal_digits),
        )

    @staticmethod
    def _apply_price_tick(view: TradingChart, tick: pandas.Series, minimal_digits: int) -> None:
        """Apply one coalesced price tick to the chart view."""
        view.set_price_text(f"${tick['price']:,.{minimal_digits}f}")
        candle_data = view.candle_data()
        if candle_data is None or candle_data.empty:
            return
        view.update_from_tick(tick)

    def handle_positions_fetched(self, all_positions: list[PerpsPosition]) -> None:
        """Forward position overlay updates to the view."""
        view = self._view()
        if view is None:
            return
        view.draw_positions(all_positions)

    def handle_orders_fetched(self, all_orders: list[OrderData]) -> None:
        """Forward order overlay updates to the view."""
        view = self._view()
        if view is None:
            return
        view.draw_orders(all_orders)

    @asyncSlot()
    async def handle_pair_changed(self, pair: str) -> None:
        """Refresh chart history and metadata after pair changes."""
        view = self._view()
        if view is None:
            return
        self._ui_controller.message_bus.blockSignals(True)
        history_dataframe, minimal_digits = await self._ui_controller.fetch_price_history()
        view.set_start_data(history_dataframe)
        view.main_chart.precision(minimal_digits)
        self._ui_controller.message_bus.blockSignals(False)

        view.set_pair_text(pair)
        view.chart_storage.tag = f"{pair}_{view.current_timeframe}"

    @asyncSlot()
    async def handle_timeframe_changed(self, timeframe_value: str) -> None:
        """Refresh chart history after timeframe changes."""
        view = self._view()
        if view is None:
            return
        history_dataframe = await self._ui_controller.fetch_price_history_for_timeframe(
            timeframe_value
        )
        view.set_start_data(history_dataframe)

    @asyncSlot()
    async def handle_exchange_changed(self) -> None:
        """Reload chart data after exchange changes."""
        await self._ui_controller.change_timeframe(self._ui_controller.current_timeframe)

    def show_search_pair(self) -> None:
        """Open or focus the pair search modal."""
        view = self._view()
        if view is None:
            return
        existing_modal = view.find_search_modal()
        if existing_modal is not None:
            existing_modal.search_input.setFocus()
            return

        search_pair_modal = view.create_search_modal(self._ui_controller)
        search_pair_modal.pair_selected.connect(self._ui_controller.change_current_pair)
        search_pair_modal.show()

    @asyncSlot()
    async def handle_infinite_chart_scroll(
        self,
        chart: Chart,
        bars_before: int,
        bars_after: int,
    ) -> None:
        """Fetch more history when the chart nears the left edge."""
        view = self._view()
        if view is None:
            return
        del bars_after
        fetch_threshold = 25
        if bars_before > fetch_threshold or view.chart_scroll_polling:
            return

        candle_timestamp = ui_utils.convert_timestamp_from_local_to_utc(
            chart.candle_data["time"].iloc[0]
        )
        view.chart_scroll_polling = True
        history = await self._ui_controller.current_exchange.fetch_price_history(
            self._ui_controller.current_pair,
            self._ui_controller.current_timeframe,
            bars_num=ui_utils.DEFAULT_BAR_NUMBERS * 3,
            to_timestamp=int(candle_timestamp.timestamp()),
        )
        view.update_data(pandas.DataFrame(history))
        view.chart_scroll_polling = False
