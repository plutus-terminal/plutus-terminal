"""Widget to visualize open orders."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableView,
    QWidget,
)
from qasync import asyncSlot

from plutus_terminal.core.exchange.types import (
    OrderData,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui.widgets.manage_order import ManageOrder

if TYPE_CHECKING:
    from collections.abc import Callable

    from plutus_terminal.core.exchange.base import ExchangeBase

HEADER_MAP = {
    "pair": "Pair",
    "trade_direction": "Side",
    "order_type": "Order Type",
    "size_stable": "Size",
    "reduce_only": "Reduce Only",
    "trigger_price": "Trigger Price",
    "buttons": "",
}

FILL_LATER = {"buttons"}


class OrdersTableModel(QAbstractTableModel):
    """Table Model to display open orders."""

    def __init__(
        self,
        format_simple_pair: Callable[[str], str],
        data: Optional[list[OrderData]] = None,
    ) -> None:
        """Initialize shared variables."""
        super().__init__()
        self._data = data if data else []
        self.headers_source = list(HEADER_MAP.keys())
        self.format_simple_pair = format_simple_pair

    def data(self, index, role):  # noqa: C901, PLR0912, PLR0911
        """Define how data is displayed."""
        current_header = self.headers_source[index.column()]

        if current_header not in FILL_LATER:
            value = self._data[index.row()][current_header]
        else:
            value = None

        if role == Qt.ItemDataRole.DisplayRole:
            if value is None:
                return None
            if current_header == "pair":
                return self.format_simple_pair(value)
            if current_header == "trade_direction":
                return value.name
            if current_header == "order_type":
                return value.name.replace("_", " ").title()
            if current_header == "trigger_price":
                if self._data[index.row()]["order_type"] is PerpsTradeType.TRIGGER_TP:
                    if self._data[index.row()]["trade_direction"] is PerpsTradeDirection.LONG:
                        sine = ">"
                    else:
                        sine = "<"
                elif self._data[index.row()]["order_type"] is PerpsTradeType.TRIGGER_SL:
                    if self._data[index.row()]["trade_direction"] is PerpsTradeDirection.LONG:
                        sine = "<"
                    else:
                        sine = ">"
                else:
                    sine = ""
                return f"{sine} ${float(round(value, 4))}"
            if isinstance(value, Decimal):
                return f"${float(round(value, 4))}"
            return str(value).title()

        if role == Qt.ItemDataRole.ForegroundRole and current_header == "trade_direction":
            if value is PerpsTradeDirection.LONG:
                return QBrush(QColor("green"))
            return QBrush(QColor("red"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        if role == Qt.ItemDataRole.UserRole:
            return self._data[index.row()]
        return None

    def headerData(self, section, orientation, role):
        """Define header data."""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return HEADER_MAP[self.headers_source[section]]
            return None
        return None

    def rowCount(self, index=None):
        """Define row count."""
        return len(self._data)

    def columnCount(self, index=None):
        """Define column count."""
        return len(HEADER_MAP)

    def update_orders(self, data: list[OrderData]) -> None:
        """Update open orders."""
        # Only reset model if data changed.
        if data == self._data:
            return
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self.format_simple_pair = new_exchange.format_simple_pair_from_pair


class OrdersTableView(QTableView):
    """Table view to display open orders."""

    row_clicked = Signal(str)

    def __init__(
        self,
        exchange: ExchangeBase,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize shared viarables."""
        super().__init__(parent)
        self._exchange = exchange
        self.clicked.connect(self.on_row_click)
        self._setup_style()

    def _setup_style(self) -> None:
        """Configure table style."""
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setShowGrid(False)

    def setModel(self, model: QAbstractItemModel) -> None:
        """Override setModel to add edit and cancel buttons."""
        super().setModel(model)
        model.modelReset.connect(self._add_buttons)

    def _add_buttons(self) -> None:
        """Add edit and cancel buttons for each row."""
        for row in range(self.model().rowCount()):
            buttons = OrderButtons()
            buttons_index = self.model().index(row, list(HEADER_MAP).index("buttons"))
            order_data = buttons_index.data(Qt.ItemDataRole.UserRole)
            buttons.cancel_button.clicked.connect(partial(self.cancel_order, order_data))
            buttons.edit_button.clicked.connect(partial(self._on_edit_order, order_data))
            self.setIndexWidget(buttons_index, buttons)
            self.setRowHeight(row, int(self.sizeHintForRow(row) * 1.1))

        self.horizontalHeader().setSectionResizeMode(
            list(HEADER_MAP).index("buttons"),
            QHeaderView.ResizeMode.Fixed,
        )

        widget = self.indexWidget(
            self.model().index(0, list(HEADER_MAP).index("buttons")),
        )
        if widget is not None:
            self.setColumnWidth(
                list(HEADER_MAP).index("buttons"),
                int(widget.sizeHint().width() * 1.1),
            )

    @asyncSlot(OrderData)
    async def cancel_order(self, order_data: OrderData) -> None:
        """Cancel order."""
        await self._exchange.cancel_order(order_data)

    def _on_edit_order(self, order_data: OrderData) -> None:
        """Handle edit button click.

        Open manage order dialog to edit order.

        Args:
            order_data (OrderData): Order to edit.
        """
        associated_position = self._exchange.get_position_associated_with_order(order_data)
        order_dialog = ManageOrder(
            order_data=deepcopy(order_data),
            exchange=self._exchange,
            associated_position=associated_position,
            parent=self,
        )
        order_dialog.set_edit_mode(True)
        order_dialog.execute_order.connect(
            lambda new_order: self.edit_order(old_order_data=order_data, new_order_data=new_order),
        )
        order_dialog.show()

    @asyncSlot(OrderData, OrderData)
    async def edit_order(self, old_order_data: OrderData, new_order_data: OrderData) -> None:
        """Edit order on exchange.

        Args:
            old_order_data (OrderData): Old order data.
            new_order_data (OrderData): New order data.
        """
        await self._exchange.edit_order(
            order_data=old_order_data,
            new_size_stable=new_order_data["size_stable"],
            new_execution_price=new_order_data["trigger_price"],
        )

    def on_row_click(self, index: QModelIndex) -> None:
        """Handle click on row."""
        self.row_clicked.emit(index.data(Qt.ItemDataRole.UserRole)["pair"])

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._exchange = new_exchange


class OrderButtons(QWidget):
    """Button to center."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize shared attributes."""
        super().__init__(parent)
        layout = QHBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.edit_button.setProperty("class", "gray")
        self.edit_button.setMinimumSize(50, 30)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "gray")
        self.cancel_button.setMinimumSize(50, 30)
        layout.addWidget(self.edit_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)
