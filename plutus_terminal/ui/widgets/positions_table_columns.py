"""Column definitions for the positions table."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionTableColumn:
    """Static metadata for a positions table column."""

    id: str
    header: str
    uses_widget: bool = False


POSITION_TABLE_COLUMNS = (
    PositionTableColumn("pair", "Pair"),
    PositionTableColumn("trade_direction", "Side"),
    PositionTableColumn("collateral_stable", "Collateral"),
    PositionTableColumn("leverage", "Lev"),
    PositionTableColumn("position_size_stable", "Size"),
    PositionTableColumn("open_price", "Avg Entry"),
    PositionTableColumn("liquidation_price", "Est. Liq. Price", uses_widget=True),
    PositionTableColumn("pnl", "PnL", uses_widget=True),
    PositionTableColumn("close", "Close", uses_widget=True),
)

POSITION_COLUMN_IDS = tuple(column.id for column in POSITION_TABLE_COLUMNS)
POSITION_COLUMN_HEADERS = {column.id: column.header for column in POSITION_TABLE_COLUMNS}
POSITION_WIDGET_COLUMN_IDS = {column.id for column in POSITION_TABLE_COLUMNS if column.uses_widget}
POSITION_PLAIN_COLUMN_IDS = tuple(
    column.id for column in POSITION_TABLE_COLUMNS if not column.uses_widget
)
POSITION_COLUMN_INDEX = {column.id: index for index, column in enumerate(POSITION_TABLE_COLUMNS)}


def get_position_column_index(column_id: str) -> int:
    """Return the model index for a column id."""
    return POSITION_COLUMN_INDEX[column_id]
