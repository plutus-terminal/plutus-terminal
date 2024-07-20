"""Dialog to manage orders."""

from decimal import Decimal
from functools import partial
from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from plutus_terminal.core.exchange.base import ExchangeBase
from plutus_terminal.core.exchange.types import (
    OrderData,
    PerpsPosition,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.extra import DoubleSpinBoxWithButton
from plutus_terminal.ui.widgets.pnl_breakdown import PnlBreakdown
from plutus_terminal.ui.widgets.top_bar_widget import TopBar


class ManageOrder(QtWidgets.QDialog):
    """Dialog to manage orders."""

    def __init__(
        self,
        order_data: OrderData,
        exchange: ExchangeBase,
        associated_position: Optional[PerpsPosition],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize dialog."""
        super().__init__(parent)
        self._order_data = order_data
        self._exchange = exchange
        self._associated_position = associated_position

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
        self.trigger_box = DoubleSpinBoxWithButton(button_text="USD")
        self.trigger_max_button = QtWidgets.QPushButton("MAX")

        self._amount_label = QtWidgets.QLabel("Amount:")
        self.amount_box = DoubleSpinBoxWithButton(button_text="USD")
        self.amount_max_button = QtWidgets.QPushButton("MAX")

        self.execute_order_button = QtWidgets.QPushButton("Execute Order")

        self._setup_widgets()
        self._setup_layout()

        self.setMinimumHeight(self.sizeHint().height())
        self.setMinimumWidth(int(self.sizeHint().width() * 1.75))

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setModal(False)
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setWindowTitle("Manage Order")

        title_color = (
            "color: rgb(255, 100, 100);"
            if self._order_data["trade_direction"].value == PerpsTradeDirection.SHORT.value
            else "color: rgb(100, 255, 100);"
        )
        self.top_bar.title.setText(
            f"{self._exchange.format_simple_pair_from_pair(self._order_data['pair'])} | "
            f"<span style='{title_color};'>{self._order_data['trade_direction'].name}</span>",
        )

        minimum_digits = ui_utils.get_minimal_digits(float(self._order_data["trigger_price"]), 4)
        self._open_price_value.setText(f"${self._order_data["trigger_price"]:,.{minimum_digits}f}")
        self._open_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._liq_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._type_group.addButton(self.limit_button, PerpsTradeType.LIMIT.value)
        self._type_group.addButton(self.tp_button, PerpsTradeType.TRIGGER_TP.value)
        self._type_group.addButton(self.sl_button, PerpsTradeType.TRIGGER_SL.value)
        self._type_group.buttonClicked.connect(self._on_type_change)
        self._type_group.button(self._order_data["order_type"].value).click()

        self._type_group.button(PerpsTradeType.LIMIT.value).setDisabled(
            self._order_data["reduce_only"],
        )

        trigger_minimum_digits = ui_utils.get_minimal_digits(
            float(self._order_data["trigger_price"]),
            4,
        )
        self.trigger_box.setDecimals(trigger_minimum_digits)
        self.trigger_box.valueChanged.connect(self.update_pnl)
        self.trigger_box.setValue(float(self._order_data["trigger_price"]))

        self.trigger_max_button.setObjectName("actionButton")
        self.trigger_max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trigger_max_button.setFixedWidth(50)
        self.trigger_max_button.clicked.connect(
            partial(self.trigger_box.setValue, float(self._order_data["trigger_price"])),
        )

        self.amount_box.setDecimals(4)
        self.amount_box.setValue(float(self._order_data["size_stable"]))
        self.amount_box.setMaximum(float(self._order_data["size_stable"]))
        self.amount_box.valueChanged.connect(self.on_quantity_change)

        self.amount_max_button.setObjectName("actionButton")
        self.amount_max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.amount_max_button.setFixedWidth(50)
        self.amount_max_button.clicked.connect(
            partial(self.amount_box.setValue, self.amount_box.maximum()),
        )

        self._info_frame.setObjectName("newsFrameQuote")
        if not self._order_data["reduce_only"]:
            self._info_frame.hide()
        self._pnl_value.pnl_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.execute_order_button.setProperty("class", "LONG")
        self.execute_order_button.setMinimumHeight(30)

        self.update_liquidation_price()

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

    def lock_order_type(self) -> None:
        """Lock order type."""
        for button in self._type_group.buttons():
            button.setEnabled(False)

    def _on_type_change(self, button: QtWidgets.QAbstractButton) -> None:
        """Handle type change."""
        button_id = self._type_group.id(button)
        trade_direction = self._order_data["trade_direction"]
        match button_id:
            case PerpsTradeType.TRIGGER_TP.value:
                if trade_direction == PerpsTradeDirection.SHORT:
                    self.trigger_box.setMinimum(0)
                    self.trigger_box.setMaximum(float(self._order_data["trigger_price"]))
                else:
                    self.trigger_box.setMaximum(100_000_000_000)
                    self.trigger_box.setMinimum(float(self._order_data["trigger_price"]))

            case PerpsTradeType.TRIGGER_SL.value:
                if trade_direction == PerpsTradeDirection.SHORT:
                    self.trigger_box.setMaximum(100_000_000_000)
                    self.trigger_box.setMinimum(float(self._order_data["trigger_price"]))
                else:
                    self.trigger_box.setMinimum(0)
                    self.trigger_box.setMaximum(float(self._order_data["trigger_price"]))

    def update_liquidation_price(self) -> None:
        """Update liquidation price."""
        if self._associated_position is None:
            self._liq_price_value.setText("--")
            return

        liquidation_price = self._exchange.get_liquidation_price(self._associated_position)
        minimal_digits = ui_utils.get_minimal_digits(float(liquidation_price), 4)
        self._liq_price_value.setText(
            f"${liquidation_price:,.{minimal_digits}f}",
        )

    def update_pnl(self, price: float) -> None:
        """Update pnl."""
        if self._associated_position is None:
            self._pnl_value.pnl_label.setText("--")
            return

        leverage = self._associated_position["leverage"]
        trade_collateral = self._associated_position["position_size_stable"] / leverage
        position_fee = self._exchange.get_position_fee(trade_collateral)
        borrow_fee = self._exchange.get_borrow_fee(self._associated_position)
        pnl_percentage = self._exchange.get_pnl_percent(self._associated_position, Decimal(price))
        pnl_usd = (trade_collateral * pnl_percentage) / 100
        pnl_usd_after_fee = pnl_usd - position_fee - borrow_fee
        pnl_percentage_after_fee = pnl_usd_after_fee * 100 / trade_collateral

        self._pnl_value.set_pnl(pnl_usd_after_fee, pnl_percentage_after_fee)
        self._pnl_value.set_tooltip_content(
            pnl_usd,
            borrow_fee,
            position_fee,
            pnl_usd_after_fee,
            push_tool_tip=False,
        )

    def on_quantity_change(self, new_quantity: float) -> None:
        """Handle quantity change.

        Args:
            new_quantity (float): New quantity.
        """
        # Update order data to reflect quantity change
        self._order_data["size_stable"] = Decimal(new_quantity)

        # If order is associated with a position, update position size
        if self._associated_position is not None:
            self._associated_position["position_size_stable"] = self._order_data["size_stable"]
        self.update_pnl(self.trigger_box.value())

    def show(self) -> None:
        """Override show method to update button position."""
        super().show()
        self.trigger_box.update_button_position()
        self.amount_box.update_button_position()
