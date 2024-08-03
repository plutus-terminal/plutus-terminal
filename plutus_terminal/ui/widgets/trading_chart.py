"""TrandingChart Widget to visualize price data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

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

from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from collections.abc import Callable

    from lightweight_charts import Chart
    from lightweight_charts.abstract import HorizontalLine

    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition

LOGGER = logging.getLogger(__name__)


class TradingChart(QWidget):
    """Trading Chart Widget."""

    timeframe_signal = Signal(str)
    pair_changed = Signal(str)

    def __init__(
        self,
        available_pairs: set[str],
        format_simple_pair: Callable[[str], str],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._available_pairs = available_pairs
        self._format_simple_pair = format_simple_pair

        self._main_layout = QVBoxLayout()

        self.top_bar = TopBar("Chart")
        self._price_label = QLabel("")

        self._main_chart = QtChart(toolbox=True)
        self._current_pair = ""
        self._position_lines: dict[int, HorizontalLine] = {}
        self._liquidation_lines: dict[int, HorizontalLine] = {}
        self._order_lines: dict[str, HorizontalLine] = {}

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

    def _config_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self.top_bar)
        self._main_layout.addWidget(self._main_chart.get_webview())

    def _config_shortcuts(self) -> None:
        """Configure shortcuts."""
        self._shortcut = QShortcut(QKeySequence("\\"), self)
        self._shortcut.activated.connect(self.show_search_pair)

    @property
    def main_chart(self) -> QtChart:
        """Returns: Main QtChart widget."""
        return self._main_chart

    @property
    def current_pair(self) -> str:
        """Returns the pair being diplayed."""
        return self._current_pair

    @current_pair.setter
    def current_pair(self, pair: str) -> None:
        """Set the current pair being displayed."""
        self._current_pair = pair
        self.set_pair_text(pair)

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

    def set_pair_text(self, pair: str) -> None:
        """Fill topbar text with pair."""
        pair_text = self._format_simple_pair(pair)
        self._main_chart.topbar["pair"].set(pair_text)  # type: ignore
        self.top_bar.title.setText(f"Chart | {pair_text}")

    def set_start_data(self, ohlcv: pandas.DataFrame, reset: bool = False) -> None:
        """Clean chart and fill with start data.

        Args:
            ohlcv (pandas.DataFrame): Open, high, low, close, volume data.
            reset (bool, optional): Reset chart for new symbol. Defaults to False.
        """
        self._main_chart.set(ohlcv)
        self._main_chart.price_scale()
        self._main_chart.fit()
        if reset:
            # TODO: remove draw_positions
            pass

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
        try:
            price = data[self.current_pair]
        except KeyError:
            LOGGER.warning(
                "Price data for %s not available. Skipping update.",
                self.current_pair,
            )
            return
        tick = pandas.Series(price)
        # Convert decimal to float
        tick["price"] = float(tick["price"])
        self._main_chart.update_from_tick(tick)

        minimal_digits = ui_utils.get_minimal_digits(tick["price"], 4)
        self._price_label.setText(f"${tick['price']:,.{minimal_digits}f}")

    def draw_positions(self, all_positions: list[PerpsPosition]) -> None:
        """Draw positions lines on the chart.

        Args:
            all_positions (list[PerpsPosition]): List of current positions.
        """
        new_positions = {
            pos["id"]: pos for pos in all_positions if pos["pair"] == self.current_pair
        }

        # Update existing positions
        for pos_id, position in new_positions.items():
            if pos_id in self._position_lines:
                # Update position if open price has changed
                current_line = self._position_lines[pos_id]
                if float(position["open_price"]) != current_line.price:
                    current_line.update(float(position["open_price"]))

                # Update liquidation line if price has changed
                liquidation_price = position["liquidation_price"]
                current_liquidation_line = self._liquidation_lines[pos_id]
                if float(liquidation_price) != current_liquidation_line.price:
                    current_liquidation_line.update(float(liquidation_price))
            else:
                # Create new position line
                new_pos_line = self._main_chart.horizontal_line(
                    float(position["open_price"]),
                    width=1,
                    color="rgb(255, 80, 80)",
                    style="dotted",
                    text=f"Open {position['trade_direction'].name.capitalize()}",
                    axis_label_visible=False,
                )
                self._position_lines[pos_id] = new_pos_line

                # Create new liquidation line
                liquidation_price = position["liquidation_price"]
                new_liquidation_line = self._main_chart.horizontal_line(
                    float(liquidation_price),
                    width=1,
                    color="rgb(225, 110, 30)",
                    style="solid",
                    text=f"Liq. {position['trade_direction'].name.capitalize()}",
                    axis_label_visible=False,
                )
                self._liquidation_lines[pos_id] = new_liquidation_line

        # Delete old lines
        positions_to_delete = [
            pos_id for pos_id in self._position_lines if pos_id not in new_positions
        ]

        for pos_id in positions_to_delete:
            self._position_lines[pos_id].delete()
            del self._position_lines[pos_id]
            self._liquidation_lines[pos_id].delete()
            del self._liquidation_lines[pos_id]

    def draw_orders(self, all_orders: list[OrderData]) -> None:
        """Draw orders lines on the chart.

        Args:
            all_orders (list[OrderData]): List of current orders.
        """
        new_orders = {
            order["id"]: order for order in all_orders if order["pair"] == self.current_pair
        }

        for order_id, order in new_orders.items():
            if order_id in self._order_lines:
                # Update order if price has changed
                current_line = self._order_lines[order_id]
                if float(order["trigger_price"]) != current_line.price:
                    current_line.update(float(order["trigger_price"]))
            else:
                # Create new order line
                self._order_lines[order_id] = self._main_chart.horizontal_line(
                    float(order["trigger_price"]),
                    width=1,
                    color="rgb(255, 80, 80)",
                    style="dashed",
                    text=f"{order['order_type'].name.replace('_', ' ').capitalize()}",
                    axis_label_visible=False,
                )

        # Delete old lines
        order_to_delete = [order_id for order_id in self._order_lines if order_id not in new_orders]

        for order_id in order_to_delete:
            self._order_lines[order_id].delete()
            del self._order_lines[order_id]

    def on_timeframe_selection(self, chart: Chart) -> None:
        """Emit signal to change timeframe."""
        timeframe_value = chart.topbar["timeframe"].value
        if timeframe_value.endswith("min"):
            timeframe_value = timeframe_value[:-3]
        else:
            timeframe_value = timeframe_value[:-2]
            timeframe_value = int(timeframe_value) * 60

        self.timeframe_signal.emit(str(timeframe_value))

    def show_search_pair(self) -> None:
        """Show search pair modal."""
        modal_children = self.findChildren(SearchPairModal)
        if modal_children:
            modal_children[0].search_input.setFocus()
            return

        search_pair_modal = SearchPairModal(
            self._available_pairs,
            self._format_simple_pair,
            self,
        )
        search_pair_modal.pair_selected.connect(self.pair_changed.emit)
        search_pair_modal.show()

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._current_pair = new_exchange.default_pair
        self._available_pairs = new_exchange.available_pairs
        self._format_simple_pair = new_exchange.format_simple_pair_from_pair


class SearchPairModal(QWidget):
    """Modal widget to search for available pairs."""

    pair_selected = Signal(str)

    def __init__(
        self,
        available_pairs: set[str],
        format_simple_pair_from_pair: Callable[[str], str],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self._available_pairs = {
            format_simple_pair_from_pair(pair): pair for pair in available_pairs
        }

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._completer = QCompleter(list(self._available_pairs.keys()))
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
        if self.search_input.text() in self._available_pairs:
            self.pair_selected.emit(self._available_pairs[self.search_input.text()])
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
