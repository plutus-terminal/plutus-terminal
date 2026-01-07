"""Dialog to manage orders."""

from decimal import Decimal
from functools import partial

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.core.exchange.types import (
    OrderData,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.decimal_spin_box import DecimalSpinBoxWithButton
from plutus_terminal.ui.widgets.pnl_breakdown import PnlBreakdown
from plutus_terminal.ui.widgets.top_bar_widget import TopBar
from plutus_terminal.controller.manage_order_controller import ManageOrderController

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.types_ import PerpsPosition

class ManageOrder(QtWidgets.QDialog):
    """Dialog to manage orders."""

    execute_order = Signal(OrderData)

    def __init__(
        self,
        order_data: OrderData,
        exchange: ExchangeBase,
        associated_position: PerpsPosition | None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize dialog."""
        super().__init__(parent)
        self.controller = ManageOrderController(order_data, exchange, associated_position)

        self._main_layout = QtWidgets.QGridLayout()

        self.top_bar = TopBar()

        self._type_group = QtWidgets.QButtonGroup()
        self.limit_button = QtWidgets.QRadioButton("Limit")
        self.tp_button = QtWidgets.QRadioButton("Take Profit")
        self.sl_button = QtWidgets.QRadioButton("Stop Loss")
        self._type_group_layout = QtWidgets.QHBoxLayout()

        self._info_frame = QtWidgets.QFrame()
        self._open_price_label = QtWidgets.QLabel("Open Price:")
        self._open_price_value = QtWidgets.QLabel("--")
        self._liq_price_label = QtWidgets.QLabel("Est. Liq. Price:")
        self._liq_price_value = QtWidgets.QLabel("--")
        self._info_layout = QtWidgets.QGridLayout()
        self._pnl_label = QtWidgets.QLabel("Est. PnL:")
        self._pnl_value = PnlBreakdown()

        self._trigger_label = QtWidgets.QLabel("Trigger Price:")
        self.trigger_box = DecimalSpinBoxWithButton(button_text="USD")
        self.trigger_max_button = QtWidgets.QPushButton("MAX")

        self._amount_label = QtWidgets.QLabel("Amount:")
        self.amount_box = DecimalSpinBoxWithButton(button_text="USD")
        self.amount_max_button = QtWidgets.QPushButton("MAX")

        self.execute_order_button = QtWidgets.QPushButton("Execute Order")

        self._setup_widgets()
        self._setup_layout()
        self._connect_signals()

        self.setMinimumHeight(self.sizeHint().height())
        self.setMinimumWidth(int(self.sizeHint().width() * 1.75))

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setModal(False)
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setWindowTitle("Manage Order")

        title_color = (
            "color: rgb(255, 100, 100);"
            if self.controller.order_data["trade_direction"].value == PerpsTradeDirection.SHORT.value
            else "color: rgb(100, 255, 100);"
        )
        self.top_bar.title.setText(
            f"{self.controller.exchange.format_simple_pair_from_pair(self.controller.order_data['pair'])} | "
            f"<span style='{title_color};'>{self.controller.order_data['trade_direction'].name}</span>",
        )

        minimum_digits = ui_utils.get_minimal_digits(float(self.controller.order_data["trigger_price"]), 4)
        self._open_price_value.setText(f"${self.controller.order_data['trigger_price']:,.{minimum_digits}f}")
        self._open_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._liq_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._type_group.addButton(self.limit_button, PerpsTradeType.LIMIT.value)
        self._type_group.addButton(self.tp_button, PerpsTradeType.TRIGGER_TP.value)
        self._type_group.addButton(self.sl_button, PerpsTradeType.TRIGGER_SL.value)
        self._type_group.button(self.controller.order_data["order_type"].value).click()

        self._type_group.button(PerpsTradeType.LIMIT.value).setDisabled(
            self.controller.order_data["reduce_only"],
        )

        trigger_minimum_digits = ui_utils.get_minimal_digits(
            float(self.controller.order_data["trigger_price"]),
            4,
        )
        self.trigger_box.setDecimals(trigger_minimum_digits)
        self.trigger_box.decimalValueChanged.connect(lambda val: self.controller.calculate_pnl(val))
        self.trigger_box.setValue(self.controller.order_data["trigger_price"])

        self.trigger_max_button.setObjectName("actionButton")
        self.trigger_max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trigger_max_button.setFixedWidth(50)
        self.trigger_max_button.clicked.connect(
            partial(self.trigger_box.setValue, self.controller.order_data["trigger_price"]),
        )

        self.amount_box.setDecimals(4)
        self.amount_box.setValue(self.controller.order_data["size_stable"])
        self.amount_box.setMaximum(self.controller.order_data["size_stable"])
        self.amount_box.decimalValueChanged.connect(self.on_quantity_change)

        self.amount_max_button.setObjectName("actionButton")
        self.amount_max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.amount_max_button.setFixedWidth(50)
        self.amount_max_button.clicked.connect(
            partial(self.amount_box.setValue, self.amount_box.maximum()),
        )

        self._info_frame.setObjectName("newsFrameQuote")
        if not self.controller.order_data["reduce_only"]:
            self._info_frame.hide()
        self._pnl_value.pnl_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.execute_order_button.setProperty("class", "LONG")
        self.execute_order_button.setMinimumHeight(30)
        self.execute_order_button.clicked.connect(self.on_execute_order)

        self.controller.calculate_liquidation_price()

    def _setup_layout(self) -> None:
        """Configure layouts."""
        self._type_group_layout.addWidget(self.limit_button)
        self._type_group_layout.addWidget(self.tp_button)
        self._type_group_layout.addWidget(self.sl_button)

        self._main_layout.addWidget(self.top_bar, 0, 0, 1, 3)
        self._main_layout.addLayout(self._type_group_layout, 1, 0, 1, 3)
        self._main_layout.addWidget(self._trigger_label, 2, 0)
        self._main_layout.addWidget(self.trigger_box, 2, 1)
        self._main_layout.addWidget(self.trigger_max_button, 2, 2)
        self._main_layout.addWidget(self._amount_label, 3, 0)
        self._main_layout.addWidget(self.amount_box, 3, 1)
        self._main_layout.addWidget(self.amount_max_button, 3, 2)

        self._info_layout.addWidget(self._open_price_label, 0, 0)
        self._info_layout.addWidget(self._open_price_value, 0, 1)
        self._info_layout.addWidget(self._liq_price_label, 1, 0)
        self._info_layout.addWidget(self._liq_price_value, 1, 1)
        self._info_layout.addWidget(self._pnl_label, 2, 0)
        self._info_layout.addWidget(self._pnl_value, 2, 1)
        self._info_frame.setLayout(self._info_layout)
        self._main_layout.addWidget(self._info_frame, 4, 0, 1, 3)

        self._main_layout.addWidget(self.execute_order_button, 5, 0, 1, 3)

        self.setLayout(self._main_layout)

    def _connect_signals(self) -> None:
        """Connect controller signals."""
        self.controller.update_pnl.connect(self._on_update_pnl)
        self.controller.update_liquidation.connect(self._on_update_liquidation)
        self.controller.execute_order_signal.connect(self._on_order_executed)

    def _on_update_pnl(self, label: str, usd_before: str, funding: str, pos_fee: str, usd_after: str, percent: str) -> None:
        """Update pnl display."""
        if label == "--":
             self._pnl_value.pnl_label.setText("--")
        else:
             # Actually update_pnl emits values even if one is "--" in my implementation.
             # Wait, controller logic: if no associated_position, emits "--", "", ...
             # View logic:
             pass

        # If usd_after is empty, it means no position.
        if not usd_after:
            self._pnl_value.pnl_label.setText("--")
            return

        self._pnl_value.set_pnl(
            Decimal(usd_after.replace("$", "")),
            Decimal(percent.replace("%", "")),
        )
        self._pnl_value.set_tooltip_content(
            Decimal(usd_before.replace("$", "")),
            Decimal(funding.replace("$", "")),
            Decimal(pos_fee.replace("$", "")),
            Decimal(usd_after.replace("$", "")),
            push_tool_tip=False,
        )

    def _on_update_liquidation(self, price_str: str) -> None:
        """Update liquidation price."""
        if price_str == "--":
            self._liq_price_value.setText("--")
        else:
            price = float(price_str)
            minimal_digits = ui_utils.get_minimal_digits(price, 4)
            self._liq_price_value.setText(f"${price:,.{minimal_digits}f}")

    def on_quantity_change(self, new_quantity: Decimal) -> None:
        """Handle quantity change."""
        self.controller.update_position_size(new_quantity)
        self.controller.calculate_pnl(self.trigger_box.value())

    def set_edit_mode(self, edit_mode: bool) -> None:
        """Set if the widget is editing or creating order."""
        self.amount_box.setDisabled(edit_mode)
        self.amount_max_button.setDisabled(edit_mode)
        for button in self._type_group.buttons():
            button.setDisabled(edit_mode)

    def on_execute_order(self) -> None:
        """Handle execute order button click."""
        self.controller.execute_order(
            Decimal(self.trigger_box.value()),
            Decimal(self.amount_box.value()),
            self._type_group.id(self._type_group.checkedButton())
        )

    def _on_order_executed(self, order: OrderData) -> None:
        """Handle execution signal from controller."""
        self.execute_order.emit(order)
        self.close()

    def show(self) -> None:
        """Override show method to update button position."""
        super().show()
        self.trigger_box.update_button_position()
        self.amount_box.update_button_position()
