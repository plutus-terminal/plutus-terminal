"""Widget to visualize open positions."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QRadioButton,
    QTableView,
    QWidget,
    QWidgetAction,
)
from qasync import asyncSlot

from plutus_terminal.core.exchange.types import OrderData, PerpsTradeType, PriceData
from plutus_terminal.core.types_ import PerpsPosition, PerpsTradeDirection
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.decimal_spin_box import (
    DecimalSpinBox,
)
from plutus_terminal.ui.widgets.manage_order import ManageOrder
from plutus_terminal.ui.widgets.pnl_breakdown import PnlBreakdown

if TYPE_CHECKING:
    from collections.abc import Callable

    from plutus_terminal.core.exchange.base import ExchangeBase

HEADER_MAP = {
    "pair": "Pair",
    "trade_direction": "Side",
    "collateral_stable": "Collateral",
    "leverage": "Lev",
    "position_size_stable": "Size",
    "open_price": "Avg Entry",
    "liquidation_price": "Est. Liq. Price",
    "pnl": "PnL",
    "close": "Close",
}

FILL_LATER = {"close", "pnl"}


class PositionsTableModel(QAbstractTableModel):
    """Table Model to display open positions."""

    def __init__(
        self,
        format_simple_pair: Callable[[str], str],
        data: Optional[list[PerpsPosition]] = None,
    ) -> None:
        """Initialize shared variables."""
        super().__init__()
        self._data = data if data else []
        self.headers_source = list(HEADER_MAP.keys())
        self.format_simple_pair = format_simple_pair

    def data(self, index, role: Qt.ItemDataRole) -> Any:  # noqa: C901, PLR0911
        """Define how data is displayed."""
        current_header = self.headers_source[index.column()]

        if current_header not in FILL_LATER:
            value = self._data[index.row()][current_header]  # type: ignore
        else:
            value = None

        if role == Qt.ItemDataRole.DisplayRole:
            if value is None:
                return None
            if current_header == "trade_direction":
                return value.name
            if current_header == "leverage":
                return f"{value}x"
            if current_header == "pair":
                # Removing the Pair prefix if any
                return self.format_simple_pair(value)
            if isinstance(value, Decimal):
                minimal_digits = ui_utils.get_minimal_digits(float(value), 3)
                return f"${value:,.{minimal_digits}f}"
            return value

        if role == Qt.ItemDataRole.ForegroundRole:
            if current_header == "trade_direction":
                if value is PerpsTradeDirection.LONG:
                    return QBrush(QColor("green"))
                return QBrush(QColor("red"))
            if current_header == "liquidation_price":
                return QBrush(QColor("orange"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        if role == Qt.ItemDataRole.FontRole and current_header == "trade_direction":
            font = QFont()
            font.setBold(True)
            return font

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

    def update_positions(self, data: list[PerpsPosition]) -> None:
        """Update open positions."""
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


class PositionsTableView(QTableView):
    """Table view to display open positions."""

    row_clicked = Signal(str)

    def __init__(
        self,
        exchange: ExchangeBase,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._exchange = exchange
        self._close_index = list(HEADER_MAP).index("close")
        self._pnl_index = list(HEADER_MAP).index("pnl")
        self._pnl_widgets: dict[str, dict[bool, PnlBreakdown]] = {}
        self._position_manager_widgets: dict[str, dict[bool, PositionManager]] = {}
        self._cached_prices: dict[str, PriceData] = {}
        self.clicked.connect(self.on_row_click)
        self._setup_style()

    def _setup_style(self) -> None:
        """Set Table style."""
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setShowGrid(False)

    def setModel(self, model: QAbstractItemModel) -> None:
        """Override setModel to add close buttons."""
        super().setModel(model)
        model.modelReset.connect(self.add_position_manager)
        model.modelReset.connect(self.create_pnl_breakdowns)

    def add_position_manager(self) -> None:
        """Add position manager for each row."""
        self.blockSignals(True)
        for row in range(self.model().rowCount()):
            index = self.model().index(row, self._close_index)
            data = index.data(Qt.ItemDataRole.UserRole)

            position_manager = ui_utils.create_stored_widget(
                PositionManager,
                self._position_manager_widgets,
                data["pair"],
                data["trade_direction"],
                position=data,
                exchange=self._exchange,
                parent=self,
            )

            self.setIndexWidget(index, position_manager)
        self.horizontalHeader().setSectionResizeMode(
            self._close_index,
            QHeaderView.ResizeMode.Fixed,
        )

        widget = self.indexWidget(self.model().index(0, self._close_index))
        if widget is not None:
            self.setColumnWidth(
                self._close_index,
                int(widget.sizeHint().width() * 1.05),
            )
        self.blockSignals(False)

    def update_cached_prices(self, cached_prices: dict[str, PriceData]) -> None:
        """Update cached prices."""
        self._cached_prices = cached_prices
        self.update_pnl(cached_prices)

    def create_pnl_breakdowns(self) -> None:
        """Create pnl breakdowns for each row."""
        self.blockSignals(True)
        for row in range(self.model().rowCount()):
            data = self.model().index(row, 0).data(Qt.ItemDataRole.UserRole)
            ui_utils.create_stored_widget(
                PnlBreakdown,
                self._pnl_widgets,
                data["pair"],
                data["trade_direction"],
            )

        self.blockSignals(False)

    def update_pnl(self, cached_prices: dict[str, PriceData]) -> None:
        """Update pries for open positions."""
        for row in range(self.model().rowCount()):
            data = self.model().index(row, 0).data(Qt.ItemDataRole.UserRole)
            try:
                current_price = cached_prices[data["pair"]]["price"]
            except KeyError:
                return

            pnl_index = self.model().index(row, self._pnl_index)

            pnl_details = self._exchange.calculate_pnl(data, current_price)

            trade_direction = data["trade_direction"]

            pnl_widget = ui_utils.get_or_create_stored_widget(
                PnlBreakdown,
                self._pnl_widgets,
                data["pair"],
                trade_direction,
                position=data,
                exchange=self._exchange,
                parent=self,
            )
            if pnl_widget is None or not isinstance(pnl_widget, PnlBreakdown):
                return

            pnl_widget.set_pnl(
                pnl_details["pnl_usd_after_fees"],
                pnl_details["pnl_percentage_after_fees"],
            )
            pnl_widget.set_tooltip_content(
                pnl_details["pnl_usd_before_fees"],
                pnl_details["funding_fee_usd"],
                pnl_details["position_fee_usd"],
                pnl_details["pnl_usd_after_fees"],
            )
            self.setIndexWidget(pnl_index, pnl_widget)
            # Set row height to 2x to make it fit in the table
            self.setRowHeight(row, int(self.sizeHintForRow(row) * 2))
        self.horizontalHeader().setSectionResizeMode(
            self._pnl_index,
            QHeaderView.ResizeMode.Fixed,
        )

        widget = self.indexWidget(self.model().index(0, self._pnl_index))
        if widget is not None:
            self.setColumnWidth(self._pnl_index, int(widget.sizeHint().width() * 1.2))

    def on_row_click(self, index: QModelIndex) -> None:
        """Handle click on row."""
        self.row_clicked.emit(index.data(Qt.ItemDataRole.UserRole)["pair"])

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._exchange = new_exchange
        self._position_manager_widgets = {}
        self._pnl_widgets = {}


class PositionManager(QWidget):
    """Position manager widget."""

    def __init__(
        self,
        position: PerpsPosition,
        exchange: ExchangeBase,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._position = position
        self._exchange = exchange

        self._main_layout = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.tp_sl_button = QPushButton("TP/SL")

        self._menu = QMenu(self)
        self._close_action = PositionCloseAction(self._position, self)

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Condifure widgets."""
        self._menu.setObjectName("floating")
        self._close_action.reduce_clicked.connect(self._on_close_reduce_clicked)
        self._close_action.set_price_clicked.connect(self.set_price_limit)
        self._menu.addAction(self._close_action)

        self.close_button.setProperty("class", "gray")
        self.close_button.setToolTip("Close Position. Right click for more options.")
        self.close_button.setMinimumSize(50, 30)
        self.close_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.close_button.customContextMenuRequested.connect(self.show_close_context)
        self.close_button.clicked.connect(self.close_position)

        self.tp_sl_button.setProperty("class", "gray")
        self.tp_sl_button.setToolTip("Open dialog to set TP/SL.")
        self.tp_sl_button.setMinimumSize(50, 30)
        self.tp_sl_button.clicked.connect(self.on_tp_sl_clicked)

    def _setup_layout(self) -> None:
        """Organize layouts."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self.close_button)
        self._main_layout.addWidget(self.tp_sl_button)
        self.setLayout(self._main_layout)

    def show_close_context(self, pos: QPoint) -> None:
        """Show context menu."""
        self._menu.exec_(
            self.close_button.mapToGlobal(self.close_button.rect().center()),
        )

    def set_price_limit(self) -> None:
        """Set price for limit trade."""
        self._close_action.set_price_limit(
            self._exchange.cached_prices[self._position["pair"]]["price"],
        )

    @asyncSlot()
    async def close_position(self) -> None:
        """Close position."""
        await self._exchange.close_position(self._position)

    @asyncSlot()
    async def _on_close_reduce_clicked(self, kwargs: dict) -> None:
        """Handle click on reduce."""
        # Close position if size matches
        if self._position["position_size_stable"] == kwargs["size"]:
            await self._exchange.close_position(self._position)
            return
        await self._exchange.create_reduce_order(**kwargs)

    def on_tp_sl_clicked(self) -> None:
        """Handle click on TP/SL."""
        order_dialog = ManageOrder(
            OrderData(
                {
                    "pair": self._position["pair"],
                    "order_type": PerpsTradeType.TRIGGER_TP,
                    "size_stable": self._position["position_size_stable"],
                    "trigger_price": self._position["open_price"],
                    "id": "_",
                    "reduce_only": True,
                    "trade_direction": self._position["trade_direction"],
                },
            ),
            exchange=self._exchange,
            associated_position=deepcopy(self._position),
            parent=self,
        )
        order_dialog.execute_order.connect(self._handle_tp_sl_clicked)
        order_dialog.show()

    @asyncSlot()
    async def _handle_tp_sl_clicked(self, order_data: OrderData) -> None:
        """Execute order on exchange.

        Args:
            order_data (OrderData): Order to execute.
        """
        await self._exchange.create_reduce_order(
            pair=order_data["pair"],
            size=order_data["size_stable"],
            trade_direction=order_data["trade_direction"],
            trade_type=order_data["order_type"],
            execution_price=order_data["trigger_price"],
        )


class PositionCloseAction(QWidgetAction):
    """Widget to close position.."""

    reduce_clicked = Signal(dict)
    set_price_clicked = Signal()

    def __init__(self, position: PerpsPosition, parent: Optional[QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)  # type: ignore
        self._position = position

        self._default_widget = QWidget(parent)
        self._main_layout = QGridLayout()
        self.type_group = QButtonGroup()
        self.market_button = QRadioButton("Market")
        self.limit_button = QRadioButton("Limit")
        self.type_group_layout = QHBoxLayout()

        self._amount_label = QLabel("Amount:")
        self._amount_box = DecimalSpinBox()
        self._amount_group = QButtonGroup()
        self._amount_group_layout = QHBoxLayout()
        for value in ("25%", "50%", "75%", "100%"):
            button = QRadioButton(value)
            self._amount_group.addButton(button)
            self._amount_group.setId(button, int(value[:-1]))
            self._amount_group_layout.addWidget(button)
        self._amount_group.buttonClicked.connect(self._set_amount_from_button)

        self._price_label = QLabel("Price:")
        self._price_box = DecimalSpinBox()
        self._price_box.setDecimals(8)
        self._price_refresh_btn = QPushButton()
        self._close_btn = QPushButton("Close Trade")
        self._close_btn.setProperty("class", "gray")
        self._close_btn.setMinimumSize(50, 30)

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.type_group.addButton(self.limit_button)
        self.type_group.addButton(self.market_button)
        self.type_group_layout.addWidget(self.market_button)
        self.type_group_layout.addWidget(self.limit_button)
        self.type_group.buttonClicked.connect(self._type_change)
        self.market_button.click()

        self._amount_box.setDecimals(8)
        self._amount_box.setRange(Decimal(1), self._position["position_size_stable"])
        self._amount_box.decimalValueChanged.connect(self._update_amount_buttons)
        self._amount_box.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._amount_group.button(100).setChecked(True)
        self._amount_box.setValue(self._position["position_size_stable"])
        self._price_box.setRange(Decimal(0), Decimal(100_000_000))
        self._price_box.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._price_refresh_btn.setProperty("class", "borderless")
        self._price_refresh_btn.setIcon(
            QIcon(":/icons/focus_icon"),
        )
        self._price_refresh_btn.setFixedWidth(25)
        self._price_refresh_btn.clicked.connect(self.set_price_clicked.emit)

        self._close_btn.clicked.connect(self._reduce_position)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addLayout(self.type_group_layout, 0, 0, 1, 3)
        self._main_layout.addWidget(self._amount_label, 1, 0)
        self._main_layout.addWidget(self._amount_box, 1, 1, 1, 2)
        self._main_layout.addLayout(self._amount_group_layout, 2, 0, 1, 3)
        self._main_layout.addWidget(self._price_label, 3, 0)
        self._main_layout.addWidget(self._price_box, 3, 1)
        self._main_layout.addWidget(self._price_refresh_btn, 3, 2)
        self._main_layout.addWidget(self._close_btn, 4, 0, 1, 3)

        self._default_widget.setLayout(self._main_layout)
        self.setDefaultWidget(self._default_widget)

    def _type_change(self, button: QRadioButton) -> None:
        """Handle type change."""
        if button == self.limit_button:
            self._price_box.setEnabled(True)
            self._price_refresh_btn.setEnabled(True)
            self.set_price_clicked.emit()
        else:
            self._price_box.setEnabled(False)
            self._price_refresh_btn.setEnabled(False)
            self._price_box.setValue(Decimal(0))

    def _set_amount_spinbox(self, amount: Decimal) -> None:
        """Set amount on spinbox."""
        self._amount_box.blockSignals(True)
        self._amount_box.setValue(amount)
        self._amount_box.blockSignals(False)

    def _update_amount_buttons(self, amount: Decimal) -> None:
        """Update amount buttons if value on spinbox matches."""
        if amount == self._position["position_size_stable"] * Decimal(0.25):
            self._amount_group.button(25).setChecked(True)
        elif amount == self._position["position_size_stable"] * Decimal(0.5):
            self._amount_group.button(50).setChecked(True)
        elif amount == self._position["position_size_stable"] * Decimal(0.75):
            self._amount_group.button(75).setChecked(True)
        elif amount == self._position["position_size_stable"]:
            self._amount_group.button(100).setChecked(True)
        else:
            button = self._amount_group.checkedButton()
            if button:
                self._amount_group.setExclusive(False)
                button.setChecked(False)
                self._amount_group.setExclusive(True)

    def _set_amount_from_button(self, button: QRadioButton) -> None:
        """Set amount from button."""
        self._set_amount_spinbox(
            Decimal(self._amount_group.id(button) / 100) * self._position["position_size_stable"],
        )

    def _reduce_position(self) -> None:
        """Reduce position."""
        reduce_args: dict[str, Any] = {}
        reduce_args["pair"] = self._position["pair"]
        reduce_args["size"] = Decimal(self._amount_box.value())
        reduce_args["trade_direction"] = self._position["trade_direction"]
        if self.limit_button.isChecked():
            reduce_args["trade_type"] = PerpsTradeType.LIMIT
            reduce_args["execution_price"] = Decimal(self._price_box.value())
        else:
            reduce_args["trade_type"] = PerpsTradeType.MARKET
            reduce_args["execution_price"] = None

        self.reduce_clicked.emit(reduce_args)

    def set_price_limit(self, price: Decimal) -> None:
        """Set price for limit trade."""
        self._price_box.setValue(price)
