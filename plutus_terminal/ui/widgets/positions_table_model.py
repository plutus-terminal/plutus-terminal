"""Model used by the positions table."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont

from plutus_terminal.core.types_ import PerpsTradeDirection
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.positions_table_columns import (
    POSITION_COLUMN_HEADERS,
    POSITION_COLUMN_IDS,
    POSITION_PLAIN_COLUMN_IDS,
    get_position_column_index,
)
from plutus_terminal.ui.widgets.positions_table_state import (
    PositionRowKey,
    build_row_lookup,
    get_changed_plain_fields,
    get_position_row_key,
    get_row_keys,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import PerpsPosition
    from plutus_terminal.ui.widgets.positions_table_state import PositionRowKey


class PositionsTableModel(QAbstractTableModel):
    """Table model to display open positions."""

    rows_updated = Signal(list)

    def __init__(
        self,
        format_simple_pair: Callable[[str], str],
        data: list[PerpsPosition] | None = None,
    ) -> None:
        """Initialize shared variables."""
        super().__init__()
        self._data = data or []
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

        column_id = POSITION_COLUMN_IDS[index.column()]
        position = self._data[index.row()]
        result: object | None = None

        if role == Qt.ItemDataRole.DisplayRole:
            result = self._display_value(column_id, position)
        elif role == Qt.ItemDataRole.ForegroundRole:
            result = self._foreground_value(column_id, position)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            result = Qt.AlignmentFlag.AlignCenter
        elif role == Qt.ItemDataRole.FontRole and column_id == "trade_direction":
            font = QFont()
            font.setBold(True)
            result = font
        elif role == Qt.ItemDataRole.UserRole:
            result = position

        return result

    def _display_value(self, column_id: str, position: PerpsPosition) -> object | None:
        value: object | None

        if column_id == "trade_direction":
            value = position["trade_direction"].name
        elif column_id == "leverage":
            value = f"{position['leverage']}x"
        elif column_id == "pair":
            value = self._format_simple_pair(position["pair"])
        elif column_id == "collateral_stable":
            value = position["collateral_stable"]
        elif column_id == "position_size_stable":
            value = position["position_size_stable"]
        elif column_id == "open_price":
            value = position["open_price"]
        else:
            value = None

        if isinstance(value, Decimal):
            minimal_digits = ui_utils.get_minimal_digits(float(value), 3)
            value = f"${value:,.{minimal_digits}f}"
        return value

    def _foreground_value(self, column_id: str, position: PerpsPosition) -> QBrush | None:
        if column_id == "trade_direction":
            if position["trade_direction"] is PerpsTradeDirection.LONG:
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
            return POSITION_COLUMN_HEADERS[POSITION_COLUMN_IDS[section]]
        return None

    def rowCount(self, _index: QModelIndex | QPersistentModelIndex | None = None) -> int:
        """Define row count."""
        return len(self._data)

    def columnCount(self, _index: QModelIndex | QPersistentModelIndex | None = None) -> int:
        """Define column count."""
        return len(POSITION_COLUMN_IDS)

    def update_positions(self, data: list[PerpsPosition]) -> None:
        """Update open positions."""
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

        changed_row_keys: list[PositionRowKey] = []
        previous_data = self._data
        self._data = data
        self._row_lookup = build_row_lookup(self._data)

        for row, (previous_position, next_position) in enumerate(
            zip(previous_data, self._data, strict=True)
        ):
            changed_fields = get_changed_plain_fields(previous_position, next_position)
            if not changed_fields and previous_position == next_position:
                continue

            changed_row_keys.append(get_position_row_key(next_position))
            for field_name in changed_fields:
                column = get_position_column_index(field_name)
                model_index = self.index(row, column)
                self.dataChanged.emit(model_index, model_index, [Qt.ItemDataRole.DisplayRole])

        if changed_row_keys:
            self.rows_updated.emit(changed_row_keys)

    def position_at_row(self, row: int) -> PerpsPosition:
        """Return the position for a row."""
        return self._data[row]

    def row_for_key(self, row_key: PositionRowKey) -> int | None:
        """Return the row index for a position key."""
        return self._row_lookup.get(row_key)

    def row_keys(self) -> list[PositionRowKey]:
        """Return the current row keys."""
        return list(self._row_keys)

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update formatting based on a new exchange."""
        self._format_simple_pair = new_exchange.format_simple_pair_from_pair
