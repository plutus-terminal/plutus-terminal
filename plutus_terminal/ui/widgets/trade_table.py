"""Widget to manage trades on exchanges."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Signal

from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
from plutus_terminal.ui.widgets.orders_table import OrdersTableModel, OrdersTableView
from plutus_terminal.ui.widgets.positions_table import (
    PositionsTableModel,
    PositionsTableView,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from decimal import Decimal

    from plutus_terminal.core.exchange.base import ExchangeBase


class TradeTable(QtWidgets.QWidget):
    """Widget to visualize and manage open trades."""

    close_trade = Signal(PerpsPosition)
    reduce_trade = Signal(dict)
    pair_clicked = Signal(str)
    order_clicked = Signal(str)
    cancel_order = Signal(OrderData)
    edit_order = Signal(OrderData)

    def __init__(
        self,
        format_simple_pair: Callable[[str], str],
        get_position_fee: Callable[[Decimal], Decimal],
        get_funding_fee: Callable[[PerpsPosition], Decimal],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared viarables."""
        super().__init__(parent)

        self._main_layout = QtWidgets.QVBoxLayout()

        self._tab_widget = QtWidgets.QTabWidget()
        self._positions_model = PositionsTableModel(format_simple_pair)
        self._positions_table = PositionsTableView(get_position_fee, get_funding_fee)
        self._orders_model = OrdersTableModel(format_simple_pair)
        self._orders_table = OrdersTableView()

        self._setup_widgets()
        self._setup_layout()

        # Set minimum height to 10% of the widget height
        self.setMinimumHeight(int(self.sizeHint().height() * 1.1))

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._positions_table.setModel(self._positions_model)
        self._positions_table.close_trade.connect(self.close_trade)
        self._positions_table.reduce_trade.connect(self.reduce_trade)
        self._positions_table.row_clicked.connect(self.pair_clicked)
        self._tab_widget.addTab(self._positions_table, "Positions (0)")

        self._orders_table.setModel(self._orders_model)
        self._orders_table.cancel_order.connect(self.cancel_order)
        self._orders_table.edit_order.connect(self.edit_order)
        self._tab_widget.addTab(self._orders_table, "Orders (0)")

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._tab_widget)
        self.setLayout(self._main_layout)

    def update_positions(self, positions: list[PerpsPosition]) -> None:
        """Update positions."""
        self._tab_widget.setTabText(0, f"Positions ({len(positions)})")
        self._positions_model.update_positions(positions)

    def update_orders(self, orders: list[OrderData]) -> None:
        """Update orders."""
        self._tab_widget.setTabText(1, f"Orders ({len(orders)})")
        self._orders_model.update_orders(orders)

    def update_prices(self, cached_prices: dict) -> None:
        """Update prices."""
        self._positions_table.update_pnl(cached_prices)

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._positions_model.on_new_exchange(new_exchange)
        self._positions_table.on_new_exchange(new_exchange)
        self._orders_model.on_new_exchange(new_exchange)
