"""Widget to visualize open positions."""

from __future__ import annotations

from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QRadioButton,
    QTableView,
    QToolTip,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from plutus_terminal.core.exchange.types import PerpsTradeType
from plutus_terminal.core.types_ import PerpsPosition, PerpsTradeDirection

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
                return float(round(value, 3))
            return value

        if role == Qt.ItemDataRole.ForegroundRole and current_header == "trade_direction":
            if value is PerpsTradeDirection.LONG:
                return QBrush(QColor("green"))
            return QBrush(QColor("red"))

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

    close_trade = Signal(PerpsPosition)
    reduce_trade = Signal(dict)
    row_clicked = Signal(str)

    def __init__(
        self,
        get_position_fee: Callable[[Decimal], Decimal],
        get_funding_fee: Callable[[PerpsPosition], Decimal],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._get_position_fee = get_position_fee
        self._get_funding_fee = get_funding_fee
        self._close_index = list(HEADER_MAP).index("close")
        self._pnl_index = list(HEADER_MAP).index("pnl")
        self._pnl_widgets: dict[str, dict[bool, PnlBreakdown]] = {}
        self._position_manager_widgets: dict[str, dict[bool, PositionManager]] = {}
        self._cached_prices: dict = {}
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

    def add_position_manager(self) -> None:
        """Add position manager for each row."""
        for row in range(self.model().rowCount()):
            index = self.model().index(row, self._close_index)
            data = index.data(Qt.ItemDataRole.UserRole)
            self._position_manager_widgets.setdefault(data["pair"], {})
            position_manager = self._position_manager_widgets[data["pair"]].get(
                data["trade_direction"].value,
                None,
            )
            if position_manager is None:
                position_manager = PositionManager(
                    position=data,
                )
                self._position_manager_widgets[data["pair"]][data["trade_direction"].value] = (
                    position_manager
                )
                position_manager.close_clicked.connect(self.close_trade.emit)
                position_manager.reduce_clicked.connect(self.reduce_trade.emit)
                position_manager.set_price_clicked.connect(self._set_current_price)
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

    def update_pnl(self, cached_prices: dict) -> None:
        """Update pries for open positions."""
        self._cached_prices = cached_prices
        for row in range(self.model().rowCount()):
            data = self.model().index(row, 0).data(Qt.ItemDataRole.UserRole)
            try:
                current_price = cached_prices[data["pair"]]["price"]
            except KeyError:
                return

            pnl_index = self.model().index(row, self._pnl_index)
            open_price = data["open_price"]
            trade_direction = data["trade_direction"]
            leverage = data["leverage"]
            trade_collateral = data["position_size_stable"] / leverage
            trade_direction_multiplier = 1 if trade_direction == PerpsTradeDirection.LONG else -1
            position_fee = self._get_position_fee(trade_collateral)
            funding_fee = self._get_funding_fee(data)
            pnl_percent = (
                ((Decimal(current_price) / open_price) - 1)
                * 100
                * leverage
                * trade_direction_multiplier
            )
            pnl_usd = (trade_collateral * pnl_percent) / 100
            pnl_usd_after_fee = pnl_usd - position_fee - funding_fee
            pnl_percent_after_fee = pnl_usd_after_fee * 100 / trade_collateral

            self._pnl_widgets.setdefault(data["pair"], {})
            pnl_widget = self._pnl_widgets[data["pair"]].get(
                trade_direction.value,
                None,
            )
            if pnl_widget is None:
                pnl_widget = PnlBreakdown()
                self._pnl_widgets[data["pair"]][trade_direction.value] = pnl_widget
            pnl_widget.set_pnl(pnl_usd_after_fee, pnl_percent_after_fee)
            pnl_widget.set_tooltip_content(
                pnl_usd,
                funding_fee,
                position_fee,
                pnl_usd_after_fee,
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

    def _set_current_price(self) -> None:
        """Set current price on Position Manager."""
        sender = self.sender()
        if not isinstance(sender, PositionManager):
            return
        sender.set_price_limit(self._cached_prices[sender._position["pair"]]["price"])  # noqa: SLF001

    def on_row_click(self, index: QModelIndex) -> None:
        """Handle click on row."""
        self.row_clicked.emit(index.data(Qt.ItemDataRole.UserRole)["pair"])

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._get_funding_fee = new_exchange.get_funding_fee
        self._get_position_fee = new_exchange.get_position_fee
        self._position_manager_widgets = {}
        self._pnl_widgets = {}


class PositionManager(QWidget):
    """Position manager widget."""

    close_clicked = Signal(dict)
    reduce_clicked = Signal(dict)
    set_price_clicked = Signal()

    def __init__(
        self,
        position: PerpsPosition,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._position = position

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
        self._close_action.reduce_clicked.connect(self.reduce_clicked.emit)
        self._close_action.set_price_clicked.connect(self.set_price_clicked.emit)
        self._menu.addAction(self._close_action)

        self.close_button.setProperty("class", "gray")
        self.close_button.setMinimumSize(50, 30)
        self.close_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.close_button.customContextMenuRequested.connect(self.show_close_context)
        self.close_button.clicked.connect(
            partial(self.close_clicked.emit, self._position),
        )

        self.tp_sl_button.setProperty("class", "gray")
        self.tp_sl_button.setMinimumSize(50, 30)

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

    def set_price_limit(self, price: Decimal) -> None:
        """Set price for limit trade."""
        self._close_action.set_price_limit(price)


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
        self._amount_box = QDoubleSpinBox()
        self._amount_group = QButtonGroup()
        self._amount_group_layout = QHBoxLayout()
        for value in ("25%", "50%", "75%", "100%"):
            button = QRadioButton(value)
            self._amount_group.addButton(button)
            self._amount_group.setId(button, int(value[:-1]))
            self._amount_group_layout.addWidget(button)
        self._amount_group.buttonClicked.connect(self._set_amount_from_button)

        self._price_label = QLabel("Price:")
        self._price_box = QDoubleSpinBox()
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
        self._amount_box.setRange(1, float(self._position["position_size_stable"]))
        self._amount_box.valueChanged.connect(self._update_amount_buttons)
        self._amount_box.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._amount_group.button(100).setChecked(True)
        self._amount_box.setValue(float(self._position["position_size_stable"]))
        self._price_box.setRange(0.0, 100_000_000)
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
            self._price_box.setValue(0.0)

    def _set_amount_spinbox(self, amount: float) -> None:
        """Set amount on spinbox."""
        self._amount_box.blockSignals(True)
        self._amount_box.setValue(amount)
        self._amount_box.blockSignals(False)

    def _update_amount_buttons(self, amount: float) -> None:
        """Update amount buttons if value on spinbox matches."""
        if amount == float(self._position["position_size_stable"]) * 0.25:
            self._amount_group.button(25).setChecked(True)
        elif amount == float(self._position["position_size_stable"]) * 0.5:
            self._amount_group.button(50).setChecked(True)
        elif amount == float(self._position["position_size_stable"]) * 0.75:
            self._amount_group.button(75).setChecked(True)
        elif amount == float(self._position["position_size_stable"]):
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
            (self._amount_group.id(button) / 100) * float(self._position["position_size_stable"]),
        )

    def _reduce_position(self) -> None:
        """Reduce position."""
        reduce_args: dict[str, Any] = {}
        reduce_args["pair"] = self._position["pair"]
        reduce_args["size"] = Decimal(self._amount_box.value())
        reduce_args["trade_direction"] = self._position["trade_direction"]
        if self.limit_button.isChecked():
            reduce_args["trade_type"] = PerpsTradeType.TRIGGER_TP
            reduce_args["execution_price"] = Decimal(self._price_box.value())
        else:
            reduce_args["trade_type"] = PerpsTradeType.MARKET
            reduce_args["execution_price"] = None

        self.reduce_clicked.emit(reduce_args)

    def set_price_limit(self, price: Decimal) -> None:
        """Set price for limit trade."""
        self._price_box.setValue(float(price))


class PnlBreakdown(QWidget):
    """Pnl breakdown widget."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._tooltip_content = ""
        self._main_layout = QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.pnl_label = QLabel()
        self.pnl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pnl_label.setObjectName("pnl")
        self._main_layout.addWidget(self.pnl_label)
        self.setLayout(self._main_layout)

        self._show_tooltip = False

    def set_pnl(self, usd: Decimal, percent: Decimal) -> None:
        """Set pnl."""
        color = "green" if percent > 0 else "red"
        text_format = (
            f"<span style='color:{color}'>{round(usd, 3)} USD<br>{round(percent, 3)}%</span>"
        )
        self.pnl_label.setText(text_format)

    def set_tooltip_content(
        self,
        pnl: Decimal,
        borrow_fee: Decimal,
        closing_fee: Decimal,
        pnl_after_fee: Decimal,
    ) -> None:
        """Set tooltip content."""
        self._tooltip_content = (
            f"PnL: {round(pnl, 3)}<br>"
            f"Borrow Fee: -{round(borrow_fee, 3)}<br>"
            f"Closing Fee: -{round(closing_fee, 3)}<br><br>"
            f"PnL After Fees: {round(pnl_after_fee, 3)}"
        )
        if self._show_tooltip:
            QToolTip.showText(
                self.mapToGlobal(self.rect().center()),
                self._tooltip_content,
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Override event to show tooltip."""
        if event.button() == Qt.MouseButton.RightButton:
            self._show_tooltip = True
            return None
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Override event to hide tooltip."""
        if event.button() == Qt.MouseButton.RightButton:
            self._show_tooltip = False
            QToolTip.hideText()
            return None
        return super().mouseReleaseEvent(event)
