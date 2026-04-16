"""Action cell used by the orders table."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from decimal import Decimal
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from qasync import asyncSlot

from plutus_terminal.ui.widgets.manage_order import ManageOrder

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import OrderData


LOGGER = logging.getLogger(__name__)


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
        self._pending_tasks: set[asyncio.Task[object]] = set()

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
        self.cancel_button.clicked.connect(self._on_cancel_order)

    def set_order_data(self, order_data: OrderData) -> None:
        """Update the widget to target a different order."""
        self._order_data = order_data

    def set_exchange(self, exchange: ExchangeBase) -> None:
        """Update the exchange dependency."""
        self._exchange = exchange

    def _on_cancel_order(self) -> None:
        """Schedule a cancel request without tying it to this widget's lifetime."""
        order_data = deepcopy(self._order_data)
        cancel_result = self._exchange.cancel_order(order_data)
        task: asyncio.Task[object]
        if isinstance(cancel_result, asyncio.Task):
            task = cancel_result
        else:
            task = asyncio.create_task(cancel_result)
        self._pending_tasks.add(task)
        task.add_done_callback(self._on_cancel_done)

    @asyncSlot()
    async def cancel_order(self) -> None:
        """Cancel order."""
        await self._exchange.cancel_order(self._order_data)

    def _on_cancel_done(self, task: asyncio.Task[object]) -> None:
        """Log background cancel failures and release task references."""
        self._pending_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            LOGGER.exception("Unexpected failure while cancelling order", exc_info=error)

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
            new_execution_price=_resolve_execution_price(self._order_data, new_order_data),
        )


def _resolve_execution_price(order_data: OrderData, new_order_data: OrderData) -> Decimal:
    """Resolve edited trigger price for regular and reduce-only TP/SL dialog payloads."""
    if "trigger_price" in new_order_data:
        return Decimal(str(new_order_data["trigger_price"]))

    order_type = order_data["order_type"]
    if order_type.name == "TRIGGER_TP":
        return Decimal(str(new_order_data["take_profit_price"]))
    if order_type.name == "TRIGGER_SL":
        return Decimal(str(new_order_data["stop_loss_price"]))

    msg = "Edited order payload missing trigger price."
    raise KeyError(msg)
