"""Widget to manage trades on exchanges."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import QTimer, Signal

from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
from plutus_terminal.ui.widgets.orders_table import OrdersTableModel, OrdersTableView
from plutus_terminal.ui.widgets.positions_table import (
    PositionsTableModel,
    PositionsTableView,
)

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


class TradeTable(QtWidgets.QWidget):
    """Widget to visualize and manage open trades."""

    order_clicked = Signal(str)
    edit_order = Signal(OrderData)

    def __init__(
        self,
        ui_controller: UIController,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared viarables."""
        super().__init__(parent)
        self._ui_controller = ui_controller
        self._exchange = ui_controller.current_exchange

        self._main_layout = QtWidgets.QVBoxLayout()

        self._tab_widget = QtWidgets.QTabWidget()
        self._positions_model = PositionsTableModel(self._exchange.format_simple_pair_from_pair)
        self._positions_table = PositionsTableView(
            self._exchange,
        )
        self._orders_model = OrdersTableModel(self._exchange.format_simple_pair_from_pair)
        self._orders_table = OrdersTableView(self._exchange)
        self._liquidation_refresh_timer = QTimer(self)
        self._orders_refresh_timer = QTimer(self)
        self._liquidation_refresh_timer.setSingleShot(True)
        self._liquidation_refresh_timer.setInterval(100)
        self._orders_refresh_timer.setSingleShot(True)
        self._orders_refresh_timer.setInterval(75)
        self._pending_orders: list[OrderData] | None = None

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()

        # Set minimum height to 10% of the widget height
        self.setMinimumHeight(int(self.sizeHint().height() * 1.1))

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._positions_table.setModel(self._positions_model)
        self._tab_widget.addTab(self._positions_table, "Positions (0)")

        self._orders_table.setModel(self._orders_model)
        self._tab_widget.addTab(self._orders_table, "Orders (0)")

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._positions_table.row_clicked.connect(self._ui_controller.change_current_pair)

        self._ui_controller.message_bus.positions_fetched.connect(self.update_positions)
        self._ui_controller.message_bus.orders_fetched.connect(self._schedule_order_refresh)
        self._ui_controller.message_bus.subscribed_prices_fetched.connect(self.update_prices)
        self._ui_controller.message_bus.balance_fetched.connect(self._schedule_liquidation_refresh)
        self._liquidation_refresh_timer.timeout.connect(self._refresh_liquidation_column)
        self._orders_refresh_timer.timeout.connect(self._flush_order_refresh)

        self._ui_controller.exchange_changed.connect(self._on_new_exchange)

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

    def _schedule_order_refresh(self, orders: list[OrderData]) -> None:
        """Coalesce bursty order updates before resetting the orders table."""
        self._pending_orders = orders
        if self._orders_refresh_timer.isActive():
            return
        self._orders_refresh_timer.start()

    def _flush_order_refresh(self) -> None:
        """Apply the latest pending order snapshot after coalescing."""
        if self._pending_orders is None:
            return
        orders = self._pending_orders
        self._pending_orders = None
        self.update_orders(orders)

    def update_prices(self, cached_prices: dict) -> None:
        """Update prices."""
        self._positions_table.update_cached_prices(cached_prices)

    def _on_new_exchange(self) -> None:
        """Update info based on new exchange."""
        exchange = self._ui_controller.current_exchange
        self._positions_model.on_new_exchange(exchange)
        self._orders_model.on_new_exchange(exchange)
        self._positions_table.on_new_exchange(exchange)
        self._orders_table.on_new_exchange(exchange)

    def _schedule_liquidation_refresh(self, _balance) -> None:  # noqa: ANN001
        """Coalesce balance events before refreshing liquidation cells."""
        if self._liquidation_refresh_timer.isActive():
            return
        self._liquidation_refresh_timer.start()

    def _refresh_liquidation_column(self) -> None:
        """Refresh only the liquidation column cells."""
        self._positions_table.refresh_liquidation_prices()
