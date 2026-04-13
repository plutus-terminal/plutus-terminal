"""Model used by the orders table."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor

from plutus_terminal.core.exchange.types import (
    PerpsTradeDirection,
    PerpsTradeType,
)
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

        column_id = ORDER_COLUMN_IDS[index.column()]
        order = self._data[index.row()]
        result: object | None = None

        if role == Qt.ItemDataRole.DisplayRole:
            result = self._display_value(column_id, order)
        elif role == Qt.ItemDataRole.ForegroundRole:
            result = self._foreground_value(column_id, order)
        elif role == Qt.ItemDataRole.ToolTipRole:
            result = self._tooltip_value(column_id, order)
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
        elif column_id == "order_kind":
            value = self._format_order_kind(order)
        elif column_id == "order_type":
            value = self._format_order_type(order)
        elif column_id == "trigger_price":
            value = self._format_trigger_price(order)
        elif column_id == "size_stable":
            value = order["size_stable"]
        elif column_id == "reduce_only":
            value = str(order["reduce_only"]).title()
        else:
            value = None

        if isinstance(value, Decimal):
            value = self._format_price(value)
        return value

    def _format_trigger_price(self, order: OrderData) -> str:
        order_extra = self._order_extra(order)
        trigger_price = order["trigger_price"]
        if trigger_price <= Decimal(0):
            return "-"

        price_text = self._format_price(trigger_price)
        trigger_price_type = (
            str(order_extra.get("trigger_price_type", "")).replace("_", " ").title()
        )
        if order["order_type"].is_stop_order:
            price_prefix = f"{trigger_price_type} @ " if trigger_price_type else ""
            return f"{price_prefix}{price_text}"

        trigger_sign = ""
        if order["order_type"] is PerpsTradeType.TRIGGER_TP:
            trigger_sign = ">" if order["trade_direction"] is PerpsTradeDirection.LONG else "<"
        elif order["order_type"] is PerpsTradeType.TRIGGER_SL:
            trigger_sign = "<" if order["trade_direction"] is PerpsTradeDirection.LONG else ">"

        return f"{trigger_sign} {price_text}".strip()

    def _format_order_kind(self, order: OrderData) -> str:
        if order["order_type"].is_stop_order:
            return "Stop"
        if order["order_type"].is_tp_sl_order:
            return "TP/SL"
        return "Regular"

    def _format_order_type(self, order: OrderData) -> str:
        order_type = order["order_type"]
        if order_type is PerpsTradeType.TRIGGER_TP:
            return "Take Profit"
        if order_type is PerpsTradeType.TRIGGER_SL:
            return "Stop Loss"
        return order_type.name.replace("_", " ").title()

    def _tooltip_value(self, column_id: str, order: OrderData) -> str | None:
        if column_id not in {"order_kind", "order_type", "trigger_price"}:
            return None

        order_extra = self._order_extra(order)
        tooltip_lines = [
            f"Order: {self._format_order_kind(order)}",
            f"Type: {self._format_order_type(order)}",
            f"Price / Trigger: {self._format_trigger_price(order)}",
        ]

        if order_extra:
            status = str(order_extra.get("algo_status") or order_extra.get("status") or "")
            if status:
                tooltip_lines.append(f"Status: {status.replace('_', ' ').title()}")

            root_status = str(order_extra.get("root_algo_order_status", ""))
            if root_status and root_status != status:
                tooltip_lines.append(f"Root Status: {root_status.replace('_', ' ').title()}")

            fee_text = self._format_fee_text(order_extra)
            if fee_text:
                tooltip_lines.append(f"Fee: {fee_text}")

            realized_pnl = self._decimal_from_extra(order_extra, "realized_pnl")
            if realized_pnl != Decimal(0):
                tooltip_lines.append(f"Realized PnL: {self._format_signed_currency(realized_pnl)}")

        return "\n".join(tooltip_lines)

    def _foreground_value(self, column_id: str, order: OrderData) -> QBrush | None:
        if column_id == "trade_direction":
            if order["trade_direction"] is PerpsTradeDirection.LONG:
                return QBrush(QColor("green"))
            return QBrush(QColor("red"))
        if column_id in {"order_kind", "order_type", "trigger_price"}:
            if order["order_type"] is PerpsTradeType.TRIGGER_TP:
                return QBrush(QColor("#1f8f55"))
            if order["order_type"] in {
                PerpsTradeType.TRIGGER_SL,
                PerpsTradeType.STOP_MARKET,
                PerpsTradeType.STOP_LIMIT,
            }:
                return QBrush(QColor("#c47c00"))
        return None

    def _order_extra(self, order: OrderData) -> dict[str, Any]:
        extra = order.get("extra", {})
        if isinstance(extra, dict):
            return extra
        return {}

    def _format_price(self, value: Decimal) -> str:
        return f"${value:,.4f}".rstrip("0").rstrip(".")

    def _format_fee_text(self, order_extra: dict[str, Any]) -> str:
        fee_value = self._decimal_from_extra(order_extra, "native_fee")
        if fee_value == Decimal(0):
            return ""
        fee_asset = str(order_extra.get("fee_asset", "")).strip()
        if fee_asset:
            return f"{self._format_decimal_text(fee_value)} {fee_asset}"
        return self._format_decimal_text(fee_value)

    def _format_signed_currency(self, value: Decimal) -> str:
        sign = "+" if value > Decimal(0) else ""
        return f"{sign}${value:,.4f}".rstrip("0").rstrip(".")

    def _decimal_from_extra(self, order_extra: dict[str, Any], key: str) -> Decimal:
        value = order_extra.get(key)
        if value in (None, ""):
            return Decimal(0)
        return Decimal(str(value))

    def _format_decimal_text(self, value: Decimal) -> str:
        return f"{value:.4f}".rstrip("0").rstrip(".")

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
                self.dataChanged.emit(
                    model_index,
                    model_index,
                    [
                        Qt.ItemDataRole.DisplayRole,
                        Qt.ItemDataRole.ForegroundRole,
                        Qt.ItemDataRole.ToolTipRole,
                    ],
                )

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
