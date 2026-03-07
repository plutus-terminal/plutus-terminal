"""Action cell used by the orders table."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from qasync import asyncSlot

from plutus_terminal.ui.widgets.manage_order import ManageOrder

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import OrderData


class OrderActionsCell(QWidget):
    """Widget used to manage an order from the orders table."""

    def __init__(
        self,
        order_data: OrderData,
        exchange: ExchangeBase,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent)
        self._order_data = order_data
        self._exchange = exchange

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setProperty("class", "gray")
        self.edit_button.setMinimumSize(50, 30)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "gray")
        self.cancel_button.setMinimumSize(50, 30)

        layout.addWidget(self.edit_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

        self.edit_button.clicked.connect(self._on_edit_order)
        self.cancel_button.clicked.connect(self.cancel_order)

    def set_order_data(self, order_data: OrderData) -> None:
        """Update the widget to target a different order."""
        self._order_data = order_data

    def set_exchange(self, exchange: ExchangeBase) -> None:
        """Update the exchange dependency."""
        self._exchange = exchange

    @asyncSlot()
    async def cancel_order(self) -> None:
        """Cancel order."""
        await self._exchange.cancel_order(self._order_data)

    def _on_edit_order(self) -> None:
        """Open manage order dialog to edit the current order."""
        associated_position = self._exchange.get_position_associated_with_order(self._order_data)
        order_dialog = ManageOrder(
            order_data=deepcopy(self._order_data),
            exchange=self._exchange,
            associated_position=associated_position,
            parent=self,
        )
        order_dialog.set_edit_mode(True)
        order_dialog.execute_order.connect(self._edit_order)
        order_dialog.show()

    @asyncSlot(object)
    async def _edit_order(self, new_order_data: OrderData) -> None:
        """Edit order on exchange."""
        await self._exchange.edit_order(
            order_data=self._order_data,
            new_size_stable=new_order_data["size_stable"],
            new_execution_price=new_order_data["trigger_price"],
        )
