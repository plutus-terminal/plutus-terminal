"""View used by the positions table."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from plutus_terminal.ui.widgets.positions_table_action_cell import PositionActionsCell
from plutus_terminal.ui.widgets.positions_table_columns import (
    POSITION_WIDGET_COLUMN_IDS,
    get_position_column_index,
)
from plutus_terminal.ui.widgets.positions_table_liquidation_cell import LiquidationPriceCell
from plutus_terminal.ui.widgets.positions_table_pnl_cell import PositionPnlCell

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import PerpsPosition, PriceData
    from plutus_terminal.ui.widgets.positions_table_model import PositionsTableModel
    from plutus_terminal.ui.widgets.positions_table_state import PositionRowKey


class PositionsTableView(QTableView):
    """Table view to display open positions."""

    row_clicked = Signal(str)

    def __init__(
        self,
        exchange: ExchangeBase,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._exchange = exchange
        self._cached_prices: dict[str, PriceData] = {}
        self._cell_widgets: dict[str, dict[PositionRowKey, QWidget]] = {
            column_id: {} for column_id in POSITION_WIDGET_COLUMN_IDS
        }
        self._pnl_column_width: int | None = None
        self._liquidation_column_width: int | None = None
        self.clicked.connect(self.on_row_click)
        self._setup_style()

    def _setup_style(self) -> None:
        """Set table style."""
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
        positions_model = cast("PositionsTableModel", model)
        positions_model.modelReset.connect(self._sync_all_cells)
        positions_model.rows_updated.connect(self._sync_rows)

    def _model(self) -> PositionsTableModel:
        return cast("PositionsTableModel", self.model())

    def _sync_all_cells(self) -> None:
        row_keys = self._model().row_keys()
        self._prune_stale_widgets(set(row_keys))
        self._sync_rows(row_keys)

    def _sync_rows(self, row_keys: list[PositionRowKey]) -> None:
        for row_key in row_keys:
            row = self._model().row_for_key(row_key)
            if row is None:
                continue

            position = self._model().position_at_row(row)
            self._sync_action_cell(row_key, row, position)
            self._sync_liquidation_cell(row_key, row, position)
            self._update_pnl_row(row_key, row, position)

        self._apply_close_column_width()
        self._apply_liquidation_column_width()
        self._apply_pnl_column_width()

    def _prune_stale_widgets(self, current_row_keys: set[PositionRowKey]) -> None:
        for registry in self._cell_widgets.values():
            stale_keys = set(registry) - current_row_keys
            for stale_key in stale_keys:
                widget = registry.pop(stale_key)
                widget.deleteLater()

    def _sync_action_cell(self, row_key: PositionRowKey, row: int, position: PerpsPosition) -> None:
        action_cell = self._cell_widgets["close"].get(row_key)
        if action_cell is None:
            action_cell = PositionActionsCell(
                position=position, exchange=self._exchange, parent=self
            )
            self._cell_widgets["close"][row_key] = action_cell

        if isinstance(action_cell, PositionActionsCell):
            action_cell.set_position(position)
            action_cell.set_exchange(self._exchange)

        close_index = self._model().index(row, get_position_column_index("close"))
        if self.indexWidget(close_index) is not action_cell:
            self.setIndexWidget(close_index, action_cell)

    def _sync_liquidation_cell(
        self, row_key: PositionRowKey, row: int, position: PerpsPosition
    ) -> None:
        liquidation_cell = self._cell_widgets["liquidation_price"].get(row_key)
        if liquidation_cell is None:
            liquidation_cell = LiquidationPriceCell(parent=self)
            self._cell_widgets["liquidation_price"][row_key] = liquidation_cell

        if isinstance(liquidation_cell, LiquidationPriceCell):
            liquidation_cell.set_price(position.get("liquidation_price"))

        liquidation_index = self._model().index(row, get_position_column_index("liquidation_price"))
        if self.indexWidget(liquidation_index) is not liquidation_cell:
            self.setIndexWidget(liquidation_index, liquidation_cell)

    def _update_pnl_row(self, row_key: PositionRowKey, row: int, position: PerpsPosition) -> None:
        current_price_data = self._cached_prices.get(position["pair"])
        if current_price_data is None and not self._exchange.use_native_position_pnl():
            return

        pnl_cell = self._cell_widgets["pnl"].get(row_key)
        if pnl_cell is None:
            pnl_cell = PositionPnlCell(parent=self)
            self._cell_widgets["pnl"][row_key] = pnl_cell

        current_price = None
        if current_price_data is not None and not self._exchange.use_native_position_pnl():
            current_price = current_price_data["price"]

        pnl_details = self._exchange.calculate_pnl(position, current_price)

        if isinstance(pnl_cell, PositionPnlCell):
            pnl_cell.set_position(position)
            pnl_cell.set_pnl_details(pnl_details)

        pnl_index = self._model().index(row, get_position_column_index("pnl"))
        if self.indexWidget(pnl_index) is not pnl_cell:
            self.setIndexWidget(pnl_index, pnl_cell)
            self.setRowHeight(row, int(self.sizeHintForRow(row) * 2))

    def _apply_close_column_width(self) -> None:
        close_index = get_position_column_index("close")
        self.horizontalHeader().setSectionResizeMode(close_index, QHeaderView.ResizeMode.Fixed)

        if self._model().rowCount() == 0:
            return
        widget = self.indexWidget(self._model().index(0, close_index))
        if widget is not None:
            self.setColumnWidth(close_index, int(widget.sizeHint().width() * 1.05))

    def _apply_liquidation_column_width(self) -> None:
        liquidation_index = get_position_column_index("liquidation_price")
        self.horizontalHeader().setSectionResizeMode(
            liquidation_index, QHeaderView.ResizeMode.Fixed
        )

        if self._liquidation_column_width is not None or self._model().rowCount() == 0:
            return
        widget = self.indexWidget(self._model().index(0, liquidation_index))
        if widget is not None:
            self._liquidation_column_width = int(widget.sizeHint().width() * 1.1)
            self.setColumnWidth(liquidation_index, self._liquidation_column_width)

    def _apply_pnl_column_width(self) -> None:
        pnl_index = get_position_column_index("pnl")
        self.horizontalHeader().setSectionResizeMode(pnl_index, QHeaderView.ResizeMode.Fixed)

        if self._pnl_column_width is not None or self._model().rowCount() == 0:
            return
        widget = self.indexWidget(self._model().index(0, pnl_index))
        if widget is not None:
            self._pnl_column_width = int(widget.sizeHint().width() * 1.2)
            self.setColumnWidth(pnl_index, self._pnl_column_width)

    def update_cached_prices(self, cached_prices: dict[str, PriceData]) -> None:
        """Update cached prices."""
        self._cached_prices = cached_prices
        self._sync_rows(self._model().row_keys())

    def refresh_liquidation_prices(self, row_keys: list[PositionRowKey] | None = None) -> None:
        """Refresh liquidation widget values for current rows."""
        for row_key in row_keys or self._model().row_keys():
            row = self._model().row_for_key(row_key)
            if row is None:
                continue
            position = self._model().position_at_row(row)
            liquidation_cell = self._cell_widgets["liquidation_price"].get(row_key)
            if liquidation_cell is None:
                self._sync_liquidation_cell(row_key, row, position)
                liquidation_cell = self._cell_widgets["liquidation_price"].get(row_key)

            if isinstance(liquidation_cell, LiquidationPriceCell):
                liquidation_cell.set_price(self._exchange.calculate_liquidation_price(position))

    def on_row_click(self, index: QModelIndex) -> None:
        """Handle click on row."""
        self.row_clicked.emit(index.data(Qt.ItemDataRole.UserRole)["pair"])

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange."""
        self._exchange = new_exchange
        self._pnl_column_width = None
        self._liquidation_column_width = None
        for registry in self._cell_widgets.values():
            for widget in registry.values():
                if isinstance(widget, PositionActionsCell):
                    widget.set_exchange(new_exchange)
