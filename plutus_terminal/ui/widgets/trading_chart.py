"""TrandingChart Widget to visualize price data."""

from __future__ import annotations

from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Optional

from lightweight_charts.widgets import QtChart
import pandas
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPixmap,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QCompleter,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot

from plutus_terminal.controller.widgets.trading_chart_controller import TradingChartController
from plutus_terminal.core.exchange.types import PerpsTradeType
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.orders_table_state import get_order_identity_key
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from lightweight_charts import Chart
    from lightweight_charts.abstract import HorizontalLine

    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition

LOGGER = logging.getLogger(__name__)


class ChartDrawingStorage:
    """Storage for chart drawing."""

    def __init__(self, tag: str) -> None:
        """Initialize storage."""
        self.tag = tag

    @property
    def value(self) -> str:
        """Returns: Storage value."""
        return self.tag


def _order_extra(order: OrderData) -> dict[str, Any]:
    extra = order.get("extra", {})
    if isinstance(extra, dict):
        return extra
    return {}


def _format_chart_order_label(order: OrderData) -> str:
    order_type = order["order_type"]
    order_extra = _order_extra(order)

    if order_type is PerpsTradeType.TRIGGER_TP:
        return "Take Profit"
    if order_type is PerpsTradeType.TRIGGER_SL:
        return "Stop Loss"
    if order_type.is_stop_order:
        trigger_price_type = str(order_extra.get("trigger_price_type", "")).replace("_", " ")
        trigger_suffix = f" ({trigger_price_type})" if trigger_price_type else ""
        order_type_label = order_type.name.replace("_", " ").title()
        return f"{order_type_label}{trigger_suffix}"
    return order_type.name.replace("_", " ").title()


def _order_line_style(order: OrderData) -> tuple[str, str]:
    order_type = order["order_type"]
    if order_type is PerpsTradeType.TRIGGER_TP:
        return "rgb(40, 167, 69)", "dashed"
    if order_type in {
        PerpsTradeType.TRIGGER_SL,
        PerpsTradeType.STOP_MARKET,
        PerpsTradeType.STOP_LIMIT,
    }:
        return "rgb(225, 140, 40)", "dashed"
    return "rgb(255, 80, 80)", "dotted"


class TradingChart(QWidget):
    """Trading Chart Widget."""

    request_more_data = Signal(int)

    def __init__(
        self,
        ui_controller: UIController,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._ui_controller = ui_controller
        self._chart_scroll_polling = False

        self._main_layout = QVBoxLayout()

        self.top_bar = TopBar("Chart")
        self._price_label = QLabel("")

        self._main_chart = QtChart(toolbox=True)
        self._position_lines: dict[int, HorizontalLine] = {}
        self._liquidation_lines: dict[int, HorizontalLine] = {}
        self._order_lines: dict[str, HorizontalLine] = {}
        self._order_line_state: dict[str, tuple[float, str, str, str]] = {}
        self._controller = TradingChartController(ui_controller, self)

        self._config_widgets()
        self._config_chart()
        self._config_layout()
        self._config_shortcuts()
        self.setLayout(self._main_layout)

        self.setMinimumHeight(self.sizeHint().height() // 2)
        self.resize(self.sizeHint())

    def _config_widgets(self) -> None:
        """Configure widgets."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.top_bar.icon.setPixmap(QPixmap(":/icons/chart_icon"))
        self.top_bar.add_widget(self._price_label)
        self._price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._price_label.setObjectName("title")

    def _config_chart(self) -> None:
        """Configure chart."""
        self._main_chart.precision(4)
        self._main_chart.layout(background_color="#131722")
        self._main_chart.legend(visible=True, font_size=14)
        self._main_chart.topbar.textbox("pair")
        self._main_chart.topbar.switcher(
            "timeframe",
            ("1min", "5min", "15min", "30min", "1hr", "4hr"),
            default="1min",
            func=self.on_timeframe_selection,
        )
        self._chart_storage = ChartDrawingStorage(
            f"{self._ui_controller.current_pair}_{self.current_timeframe}",
        )
        if self._main_chart.toolbox is not None:
            self._main_chart.toolbox.save_drawings_under(self._chart_storage)
        self._main_chart.events.range_change += self._controller.handle_infinite_chart_scroll

    def _config_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self.top_bar)
        self._main_layout.addWidget(self._main_chart.get_webview())

    def _config_shortcuts(self) -> None:
        """Configure shortcuts."""
        self._search_shortcut = QShortcut(QKeySequence("\\"), self)
        self._search_shortcut.activated.connect(self.show_search_pair)
        self._fit_chart_shortcut = QShortcut(QKeySequence("f"), self)
        self._fit_chart_shortcut.activated.connect(partial(self._main_chart.fit))

    @property
    def main_chart(self) -> QtChart:
        """Returns: Main QtChart widget."""
        return self._main_chart

    @property
    def chart_storage(self) -> ChartDrawingStorage:
        """Expose chart drawing storage for the controller."""
        return self._chart_storage

    @property
    def chart_scroll_polling(self) -> bool:
        """Expose polling flag for the controller."""
        return self._chart_scroll_polling

    @chart_scroll_polling.setter
    def chart_scroll_polling(self, value: bool) -> None:
        """Update polling flag from the controller."""
        self._chart_scroll_polling = value

    @property
    def current_timeframe(self) -> str:
        """Returns the current timeframe."""
        timeframe_value = self._main_chart.topbar["timeframe"].value
        if timeframe_value.endswith("min"):
            timeframe_value = timeframe_value[:-3]
        else:
            timeframe_value = timeframe_value[:-2]
            timeframe_value = int(timeframe_value) * 60

        return str(timeframe_value)

    def candle_data(self) -> pandas.DataFrame | None:
        """Return the current chart candle data."""
        return self._main_chart.candle_data

    def update_from_tick(self, tick: pandas.Series) -> None:
        """Apply a normalized price tick to the chart."""
        self._main_chart.update_from_tick(tick)

    def set_price_text(self, text: str) -> None:
        """Render the live price label text."""
        self._price_label.setText(text)

    def set_pair_text(self, pair: str) -> None:
        """Fill topbar text with pair."""
        pair_text = self._ui_controller.format_simple_pair_from_pair(pair)
        self._main_chart.topbar["pair"].set(pair_text)  # type: ignore
        self.top_bar.title.setText(f"Chart | {pair_text}")

    def set_start_data(self, ohlcv: pandas.DataFrame) -> None:
        """Clean chart and fill with start data.

        Args:
            ohlcv (pandas.DataFrame): Open, high, low, close, volume data.
            keep_drawings (bool): Keep drawings on chart.
        """
        self._clear_overlay_lines()
        # Convert to local timezone
        ohlcv["date"] = ohlcv["date"].apply(ui_utils.convert_timestamp_to_local_timezone)
        self._main_chart.set(ohlcv)
        self._main_chart.price_scale()
        if self._main_chart.toolbox is None:
            return
        self._main_chart.toolbox.load_drawings(self._chart_storage.tag)
        if self._main_chart.toolbox.drawings is not None:
            self._main_chart.toolbox.reposition_on_time()

    def update_data(self, ohlcv: pandas.DataFrame) -> None:
        """Update chart data.

        Args:
            ohlcv (pandas.DataFrame): Open, high, low, close, volume data.
        """
        # Convert to local timezone
        ohlcv["date"] = ohlcv["date"].apply(ui_utils.convert_timestamp_to_local_timezone)
        current_data = self._main_chart.candle_data.copy()
        current_data = current_data.rename(columns={"time": "date"})
        current_data["date"] = current_data["date"].apply(lambda x: pandas.to_datetime(x, unit="s"))
        updated_data = pandas.concat([ohlcv, current_data]).drop_duplicates().reset_index(drop=True)
        self._main_chart.set(updated_data, keep_drawings=True)

    def update_chart_ohlcv(self, ohlcv: pandas.DataFrame) -> None:
        """Update the chart with the ohlcv data.

        Args:
            ohlcv (pandas.DataFrame): Open, high, low, close, volume data.
        """
        self._main_chart.update(ohlcv)  # type: ignore

    def update_chart_tick(self, data: dict) -> None:
        """Update the chart with the price tick.

        Args:
            data (dict): Data with all available prices.
        """
        self._controller.handle_price_tick(data)

    def draw_positions(self, all_positions: list[PerpsPosition]) -> None:
        """Draw positions lines on the chart.

        Args:
            all_positions (list[PerpsPosition]): List of current positions.
        """
        new_positions = {
            pos["id"]: pos
            for pos in all_positions
            if pos["pair"] == self._ui_controller.current_pair
        }

        # Update existing positions
        for pos_id, position in new_positions.items():
            if pos_id in self._position_lines:
                # Update position if open price has changed
                current_line = self._position_lines[pos_id]
                try:
                    if float(position["open_price"]) != current_line.price:
                        current_line.update(float(position["open_price"]))
                except RuntimeError:
                    LOGGER.debug("Recreating stale position line for %s", pos_id)
                    self._safe_delete_line(current_line)
                    del self._position_lines[pos_id]
                    current_line = self._create_position_line(position)
                    self._position_lines[pos_id] = current_line

                # Update liquidation line if price has changed
                liquidation_price = position["liquidation_price"]
                current_liquidation_line = self._liquidation_lines[pos_id]
                try:
                    if float(liquidation_price) != current_liquidation_line.price:
                        current_liquidation_line.update(float(liquidation_price))
                except RuntimeError:
                    LOGGER.debug("Recreating stale liquidation line for %s", pos_id)
                    self._safe_delete_line(current_liquidation_line)
                    del self._liquidation_lines[pos_id]
                    current_liquidation_line = self._create_liquidation_line(position)
                    self._liquidation_lines[pos_id] = current_liquidation_line
            else:
                self._position_lines[pos_id] = self._create_position_line(position)
                self._liquidation_lines[pos_id] = self._create_liquidation_line(position)

        # Delete old lines
        positions_to_delete = [
            pos_id for pos_id in self._position_lines if pos_id not in new_positions
        ]

        for pos_id in positions_to_delete:
            self._safe_delete_line(self._position_lines[pos_id])
            del self._position_lines[pos_id]
            self._safe_delete_line(self._liquidation_lines[pos_id])
            del self._liquidation_lines[pos_id]

    def draw_orders(self, all_orders: list[OrderData]) -> None:
        """Draw orders lines on the chart.

        Args:
            all_orders (list[OrderData]): List of current orders.
        """
        new_orders = {
            get_order_identity_key(order): order
            for order in all_orders
            if order["pair"] == self._ui_controller.current_pair and order["trigger_price"] > 0
        }

        for order_id, order in new_orders.items():
            order_label = _format_chart_order_label(order)
            line_color, line_style = _order_line_style(order)
            line_state = (float(order["trigger_price"]), line_color, line_style, order_label)
            current_line = self._order_lines.get(order_id)
            if current_line is not None and self._order_line_state.get(order_id) == line_state:
                continue
            if current_line is not None:
                self._safe_delete_line(current_line)

            self._order_lines[order_id] = self._main_chart.horizontal_line(
                line_state[0],
                width=1,
                color=line_state[1],
                style=line_state[2],
                text=line_state[3],
                axis_label_visible=False,
            )
            self._order_line_state[order_id] = line_state

        # Delete old lines
        order_to_delete = [order_id for order_id in self._order_lines if order_id not in new_orders]

        for order_id in order_to_delete:
            self._safe_delete_line(self._order_lines[order_id])
            del self._order_lines[order_id]
            self._order_line_state.pop(order_id, None)

    def _clear_overlay_lines(self) -> None:
        """Clear cached chart overlays before resetting chart data."""
        for line in self._order_lines.values():
            self._safe_delete_line(line)
        for line in self._position_lines.values():
            self._safe_delete_line(line)
        for line in self._liquidation_lines.values():
            self._safe_delete_line(line)
        self._order_lines.clear()
        self._position_lines.clear()
        self._liquidation_lines.clear()
        self._order_line_state.clear()

    def _create_position_line(self, position: PerpsPosition) -> HorizontalLine:
        """Create an open-position line on the chart."""
        return self._main_chart.horizontal_line(
            float(position["open_price"]),
            width=1,
            color="rgb(255, 80, 80)",
            style="dotted",
            text=f"Open {position['trade_direction'].name.capitalize()}",
            axis_label_visible=False,
        )

    def _create_liquidation_line(self, position: PerpsPosition) -> HorizontalLine:
        """Create a liquidation line on the chart."""
        return self._main_chart.horizontal_line(
            float(position["liquidation_price"]),
            width=1,
            color="rgb(225, 110, 30)",
            style="solid",
            text=f"Est. Liq {position['trade_direction'].name.capitalize()}",
            axis_label_visible=False,
        )

    @staticmethod
    def _safe_delete_line(line: HorizontalLine) -> None:
        """Delete a chart line while tolerating stale-handle failures."""
        try:
            line.delete()
        except RuntimeError:
            LOGGER.debug("Skipping delete for stale chart line", exc_info=True)

    async def on_timeframe_selection(self, chart: Chart) -> None:
        """Emit signal to change timeframe."""
        timeframe_value = chart.topbar["timeframe"].value
        if timeframe_value.endswith("min"):
            timeframe_value = timeframe_value[:-3]
        else:
            timeframe_value = timeframe_value[:-2]
            timeframe_value = int(timeframe_value) * 60

        self._chart_storage.tag = f"{self._ui_controller.current_pair}_{timeframe_value}"
        await self._ui_controller.change_timeframe(str(timeframe_value))

    def show_search_pair(self) -> None:
        """Show search pair modal."""
        self._controller.show_search_pair()

    def find_search_modal(self) -> SearchPairModal | None:
        """Return the existing search modal when present."""
        modal_children = self.findChildren(SearchPairModal)
        if not modal_children:
            return None
        return modal_children[0]

    def create_search_modal(self, ui_controller: UIController) -> SearchPairModal:
        """Create a search modal bound to this chart."""
        return SearchPairModal(ui_controller, self)


class SearchPairModal(QWidget):
    """Modal widget to search for available pairs."""

    pair_selected = Signal(str)

    def __init__(
        self,
        ui_controller: UIController,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self._ui_controller = ui_controller
        self._formated_available_pairs = {
            self._ui_controller.format_simple_pair_from_pair(pair): pair
            for pair in ui_controller.exchange_available_pairs
        }

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._completer = QCompleter(list(self._formated_available_pairs.keys()))
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)

        self._main_layout = QVBoxLayout(self)
        self.search_input = VimLineEdit(self._completer)
        self.search_input.setFixedHeight(40)
        self.search_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.search_input.setPlaceholderText("Search for pair")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setCursor(Qt.CursorShape.ArrowCursor)
        self.search_input.returnPressed.connect(self.on_search_pair)

        self.parent().installEventFilter(self)

        self.close_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.close_shortcut.activated.connect(self.close)

        self._main_layout.addWidget(self.search_input)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def on_search_pair(self) -> None:
        """Emit pair selected signal if search input is valid."""
        if self.search_input.text() in self._formated_available_pairs:
            self.pair_selected.emit(self._formated_available_pairs[self.search_input.text()])
        self.close()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter resize events.

        Args:
            watched: The object being watched
            event: The event being watched

        Returns:
            bool: True if the event was handled.
        """
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.resize(self.parent().size())  # type: ignore
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Close modal when clicked outside of the image."""
        if not self.search_input.geometry().contains(event.pos()):
            self.close()
        return super().mousePressEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Raise and resize modal widget."""
        self.raise_()
        self.resize(self.parent().size())  # type: ignore
        self.search_input.setFocus()
        return super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Delete widget on close."""
        self.deleteLater()
        return super().closeEvent(event)


class VimLineEdit(QLineEdit):
    """Line edit with vim motions for completer."""

    def __init__(self, completer: QCompleter, parent: Optional[QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._completer = completer
        self.setCompleter(self._completer)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Keypress event for Tab and Shift+Tab."""
        if event.key() == Qt.Key.Key_J and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Simulate down/up arrow key press to navigate the completer popup
            new_event = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Down,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.postEvent(self._completer.popup(), new_event)
        elif (
            event.key() == Qt.Key.Key_K and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            # Simulate down/up arrow key press to navigate the completer popup
            new_event = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Up,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.postEvent(self._completer.popup(), new_event)
        elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if self._completer.popup().isVisible():
                current_index = self._completer.popup().currentIndex()
                # Select the item if there is one
                if not current_index.isValid() and self.text():
                    index = self._completer.completionModel().index(0, 0)
                    if index.isValid():
                        self.setText(self._completer.completionModel().data(index))
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
