"""View used by the orders table."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from plutus_terminal.ui.widgets.orders_table_action_cell import OrderActionsCell
from plutus_terminal.ui.widgets.orders_table_columns import (
    ORDER_WIDGET_COLUMN_IDS,
    get_order_column_index,
)

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import OrderData
    from plutus_terminal.ui.widgets.orders_table_model import OrdersTableModel
    from plutus_terminal.ui.widgets.orders_table_state import OrderRowKey


class OrdersTableView(QTableView):
    """Table view to display open orders."""

    row_clicked = Signal(str)

    def __init__(self, exchange: ExchangeBase, parent: QWidget | None = None) -> None:
        """Initialize shared variables."""
        super().__init__(parent)
        self._exchange = exchange
        self._cell_widgets: dict[str, dict[OrderRowKey, QWidget]] = {
            column_id: {} for column_id in ORDER_WIDGET_COLUMN_IDS
        }
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

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Override setModel to attach dynamic cells."""
        super().setModel(model)
        if model is None:
            return
        orders_model = cast("OrdersTableModel", model)
        orders_model.modelReset.connect(self._sync_all_cells)
        orders_model.rows_updated.connect(self._sync_rows)

    def _model(self) -> OrdersTableModel:
        return cast("OrdersTableModel", self.model())

    def _sync_all_cells(self) -> None:
        row_keys = self._model().row_keys()
        self._prune_stale_widgets(set(row_keys))
        self._sync_rows(row_keys)

    def _sync_rows(self, row_keys: list[OrderRowKey]) -> None:
        for row_key in row_keys:
            row = self._model().row_for_key(row_key)
            if row is None:
                continue

            order = self._model().order_at_row(row)
            self._sync_action_cell(row_key, row, order)

        self._apply_buttons_column_width()

    def _prune_stale_widgets(self, current_row_keys: set[OrderRowKey]) -> None:
        for registry in self._cell_widgets.values():
            stale_keys = set(registry) - current_row_keys
            for stale_key in stale_keys:
                widget = registry.pop(stale_key)
                widget.deleteLater()

    def _sync_action_cell(self, row_key: OrderRowKey, row: int, order: OrderData) -> None:
        action_cell = self._cell_widgets["buttons"].get(row_key)
        if action_cell is None:
            action_cell = OrderActionsCell(order_data=order, exchange=self._exchange, parent=self)
            self._cell_widgets["buttons"][row_key] = action_cell

        if isinstance(action_cell, OrderActionsCell):
            action_cell.set_order_data(order)
            action_cell.set_exchange(self._exchange)

        buttons_index = self._model().index(row, get_order_column_index("buttons"))
        if self.indexWidget(buttons_index) is not action_cell:
            self.setIndexWidget(buttons_index, action_cell)
            self.setRowHeight(row, int(self.sizeHintForRow(row) * 1.1))

    def _apply_buttons_column_width(self) -> None:
        buttons_index = get_order_column_index("buttons")
        self.horizontalHeader().setSectionResizeMode(buttons_index, QHeaderView.ResizeMode.Fixed)

        if self._model().rowCount() == 0:
            return
        widget = self.indexWidget(self._model().index(0, buttons_index))
        if widget is not None:
            self.setColumnWidth(buttons_index, int(widget.sizeHint().width() * 1.1))

    def on_row_click(self, index: QModelIndex) -> None:
        """Handle click on row."""
        self.row_clicked.emit(index.data(Qt.ItemDataRole.UserRole)["pair"])

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange."""
        self._exchange = new_exchange
        for registry in self._cell_widgets.values():
            for widget in registry.values():
                if isinstance(widget, OrderActionsCell):
                    widget.set_exchange(new_exchange)
