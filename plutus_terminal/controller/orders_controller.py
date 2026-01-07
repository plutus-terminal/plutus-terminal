"""Controller for OrdersTable."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

from plutus_terminal.core.exchange.types import OrderData

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


class OrdersController(QObject):
    """Controller for OrdersTable."""

    refresh_table = Signal()
    exchange_updated = Signal(object) # ExchangeBase

    def __init__(self, ui_controller: UIController) -> None:
        """Initialize controller.

        Args:
            ui_controller (UIController): UI Controller.
        """
        super().__init__()
        self.ui_controller = ui_controller
        self.exchange = ui_controller.current_exchange
        self.orders: list[OrderData] = []

        self.connect_signals()

    def connect_signals(self) -> None:
        """Connect signals."""
        self.ui_controller.exchange_changed.connect(self.on_exchange_changed)
        # Note: UIController doesn't have a direct 'orders_changed' signal,
        # but it has `message_bus.orders_fetched`.
        self.ui_controller.message_bus.orders_fetched.connect(self.on_orders_fetched)

    def on_orders_fetched(self, orders: list[OrderData]) -> None:
        """Handle fetched orders.

        Args:
            orders (list[OrderData]): Fetched orders.
        """
        self.orders = orders
        self.refresh_table.emit()

    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel order.

        Args:
            order_data (OrderData): Order data.
        """
        await self.exchange.cancel_order(order_data)

    async def edit_order(self, old_order_data: OrderData, new_order_data: OrderData) -> None:
        """Edit order.

        Args:
            old_order_data (OrderData): Old order data.
            new_order_data (OrderData): New order data.
        """
        await self.exchange.edit_order(
            order_data=old_order_data,
            new_size_stable=new_order_data["size_stable"],
            new_execution_price=new_order_data["trigger_price"],
        )

    def get_associated_position(self, order_data: OrderData) -> Any:
        """Get position associated with order.

        Args:
            order_data (OrderData): Order data.

        Returns:
            Any: Associated position.
        """
        return self.exchange.get_position_associated_with_order(order_data)

    @asyncSlot()
    async def on_exchange_changed(self) -> None:
        """Handle exchange change."""
        self.exchange = self.ui_controller.current_exchange
        self.exchange_updated.emit(self.exchange)
        # We might need to refresh table or clear it?
        # Usually fetching orders happens automatically after exchange change.
        self.orders = []
        self.refresh_table.emit()
