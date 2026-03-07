"""Model used by the orders table."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor

from plutus_terminal.core.exchange.types import PerpsTradeDirection, PerpsTradeType
from plutus_terminal.ui.widgets.orders_table_columns import (
    ORDER_COLUMN_HEADERS,
    ORDER_COLUMN_IDS,
    get_order_column_index,
)
from plutus_terminal.ui.widgets.orders_table_state import (
    OrderRowKey,
    build_row_lookup,
    get_changed_plain_fields,
    get_order_row_key,
    get_row_keys,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import OrderData
    from plutus_terminal.ui.widgets.orders_table_state import OrderRowKey


class OrdersTableModel(QAbstractTableModel):
    """Table model to display open orders."""

    rows_updated = Signal(list)

    def __init__(
        self,
        format_simple_pair: Callable[[str], str],
        data: list[OrderData] | None = None,
    ) -> None:
        """Initialize shared variables."""
        super().__init__()
        self._data = data if data else []
        self._row_lookup = build_row_lookup(self._data)
        self._row_keys = get_row_keys(self._data)
        self._format_simple_pair = format_simple_pair

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        """Define how data is displayed."""
        if not index.isValid():
            return None

        column_id = ORDER_COLUMN_IDS[index.column()]
        order = self._data[index.row()]
        result: object | None = None

        if role == Qt.ItemDataRole.DisplayRole:
            result = self._display_value(column_id, order)
        elif role == Qt.ItemDataRole.ForegroundRole:
            result = self._foreground_value(column_id, order)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            result = Qt.AlignmentFlag.AlignCenter
        elif role == Qt.ItemDataRole.UserRole:
            result = order

        return result

    def _display_value(self, column_id: str, order: OrderData) -> object | None:
        value: object | None

        if column_id == "pair":
            value = self._format_simple_pair(order["pair"])
        elif column_id == "trade_direction":
            value = order["trade_direction"].name
        elif column_id == "order_type":
            value = order["order_type"].name.replace("_", " ").title()
        elif column_id == "trigger_price":
            value = self._format_trigger_price(order)
        elif column_id == "size_stable":
            value = order["size_stable"]
        elif column_id == "reduce_only":
            value = str(order["reduce_only"]).title()
        else:
            value = None

        if isinstance(value, Decimal):
            value = f"${float(round(value, 4))}"
        return value

    def _format_trigger_price(self, order: OrderData) -> str:
        trigger_sign = ""
        if order["order_type"] is PerpsTradeType.TRIGGER_TP:
            trigger_sign = ">" if order["trade_direction"] is PerpsTradeDirection.LONG else "<"
        elif order["order_type"] is PerpsTradeType.TRIGGER_SL:
            trigger_sign = "<" if order["trade_direction"] is PerpsTradeDirection.LONG else ">"

        return f"{trigger_sign} ${float(round(order['trigger_price'], 4))}"

    def _foreground_value(self, column_id: str, order: OrderData) -> QBrush | None:
        if column_id == "trade_direction":
            if order["trade_direction"] is PerpsTradeDirection.LONG:
                return QBrush(QColor("green"))
            return QBrush(QColor("red"))
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        """Define header data."""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ORDER_COLUMN_HEADERS[ORDER_COLUMN_IDS[section]]
        return None

    def rowCount(self, _index: QModelIndex | QPersistentModelIndex | None = None) -> int:
        """Define row count."""
        return len(self._data)

    def columnCount(self, _index: QModelIndex | QPersistentModelIndex | None = None) -> int:
        """Define column count."""
        return len(ORDER_COLUMN_IDS)

    def update_orders(self, data: list[OrderData]) -> None:
        """Update open orders."""
        if data == self._data:
            return

        new_row_keys = get_row_keys(data)
        if new_row_keys != self._row_keys:
            self.beginResetModel()
            self._data = data
            self._row_keys = new_row_keys
            self._row_lookup = build_row_lookup(self._data)
            self.endResetModel()
            return

        changed_row_keys: list[OrderRowKey] = []
        previous_data = self._data
        self._data = data
        self._row_lookup = build_row_lookup(self._data)

        for row, (previous_order, next_order) in enumerate(
            zip(previous_data, self._data, strict=True)
        ):
            changed_fields = get_changed_plain_fields(previous_order, next_order)
            if not changed_fields and previous_order == next_order:
                continue

            changed_row_keys.append(get_order_row_key(next_order))
            for field_name in changed_fields:
                column = get_order_column_index(field_name)
                model_index = self.index(row, column)
                self.dataChanged.emit(model_index, model_index, [Qt.ItemDataRole.DisplayRole])

        if changed_row_keys:
            self.rows_updated.emit(changed_row_keys)

    def order_at_row(self, row: int) -> OrderData:
        """Return the order for a row."""
        return self._data[row]

    def row_for_key(self, row_key: OrderRowKey) -> int | None:
        """Return the row index for an order key."""
        return self._row_lookup.get(row_key)

    def row_keys(self) -> list[OrderRowKey]:
        """Return the current row keys."""
        return list(self._row_keys)

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update formatting based on a new exchange."""
        self._format_simple_pair = new_exchange.format_simple_pair_from_pair
