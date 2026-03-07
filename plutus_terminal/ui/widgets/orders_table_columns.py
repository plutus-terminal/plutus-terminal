"""Column definitions for the orders table."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrderTableColumn:
    """Static metadata for an orders table column."""

    id: str
    header: str
    uses_widget: bool = False


ORDER_TABLE_COLUMNS = (
    OrderTableColumn("pair", "Pair"),
    OrderTableColumn("trade_direction", "Side"),
    OrderTableColumn("order_type", "Order Type"),
    OrderTableColumn("size_stable", "Size"),
    OrderTableColumn("reduce_only", "Reduce Only"),
    OrderTableColumn("trigger_price", "Trigger Price"),
    OrderTableColumn("buttons", "", uses_widget=True),
)

ORDER_COLUMN_IDS = tuple(column.id for column in ORDER_TABLE_COLUMNS)
ORDER_COLUMN_HEADERS = {column.id: column.header for column in ORDER_TABLE_COLUMNS}
ORDER_PLAIN_COLUMN_IDS = tuple(
    column.id for column in ORDER_TABLE_COLUMNS if not column.uses_widget
)
ORDER_WIDGET_COLUMN_IDS = {column.id for column in ORDER_TABLE_COLUMNS if column.uses_widget}
ORDER_COLUMN_INDEX = {column.id: index for index, column in enumerate(ORDER_TABLE_COLUMNS)}


def get_order_column_index(column_id: str) -> int:
    """Return the model index for a column id."""
    return ORDER_COLUMN_INDEX[column_id]
