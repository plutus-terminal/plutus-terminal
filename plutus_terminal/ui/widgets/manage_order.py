"""Dialog to manage orders."""

from decimal import Decimal
from functools import partial
from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.core.exchange.base import ExchangeBase
from plutus_terminal.core.exchange.types import (
    OrderData,
    PerpsPosition,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.decimal_spin_box import DecimalSpinBoxWithButton
from plutus_terminal.ui.widgets.pnl_breakdown import PnlBreakdown
from plutus_terminal.ui.widgets.top_bar_widget import TopBar


class ManageOrder(QtWidgets.QDialog):
    """Dialog to manage orders."""

    execute_order = Signal(object)

    def __init__(
        self,
        order_data: OrderData,
        exchange: ExchangeBase,
        associated_position: PerpsPosition | None,
        parent: QtWidgets.QWidget | None = None,
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
        self.trigger_box = DecimalSpinBoxWithButton(button_text="USD")
        self.trigger_max_button = QtWidgets.QPushButton("MAX")
        self._pair_order_checkbox = QtWidgets.QCheckBox()
        self._secondary_trigger_label = QtWidgets.QLabel("Stop Loss Price:")
        self.secondary_trigger_box = DecimalSpinBoxWithButton(button_text="USD")
        self.secondary_trigger_max_button = QtWidgets.QPushButton("MAX")

        self._amount_label = QtWidgets.QLabel("Amount:")
        self.amount_box = DecimalSpinBoxWithButton(button_text="USD")
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
        self._open_price_value.setText(f"${self._order_data['trigger_price']:,.{minimum_digits}f}")
        self._open_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._liq_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._type_group.addButton(self.limit_button, PerpsTradeType.LIMIT.value)
        self._type_group.addButton(self.tp_button, PerpsTradeType.TRIGGER_TP.value)
        self._type_group.addButton(self.sl_button, PerpsTradeType.TRIGGER_SL.value)
        self._type_group.button(self._order_data["order_type"].value).click()
        self._type_group.buttonClicked.connect(self._update_tp_sl_mode_ui)

        self._type_group.button(PerpsTradeType.LIMIT.value).setDisabled(
            self._order_data["reduce_only"],
        )

        trigger_minimum_digits = ui_utils.get_minimal_digits(
            float(self._order_data["trigger_price"]),
            4,
        )
        self.trigger_box.setDecimals(trigger_minimum_digits)
        self.trigger_box.decimalValueChanged.connect(self.update_pnl)
        self.trigger_box.setValue(self._order_data["trigger_price"])

        self.trigger_max_button.setObjectName("actionButton")
        self.trigger_max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trigger_max_button.setFixedWidth(50)
        self.trigger_max_button.clicked.connect(
            partial(self.trigger_box.setValue, self._order_data["trigger_price"]),
        )

        self._pair_order_checkbox.toggled.connect(self._toggle_secondary_trigger)

        self.secondary_trigger_box.setDecimals(trigger_minimum_digits)
        self.secondary_trigger_box.setValue(self._order_data["trigger_price"])

        self.secondary_trigger_max_button.setObjectName("actionButton")
        self.secondary_trigger_max_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.secondary_trigger_max_button.setFixedWidth(50)
        self.secondary_trigger_max_button.clicked.connect(
            partial(self.secondary_trigger_box.setValue, self._order_data["trigger_price"]),
        )

        self.amount_box.setDecimals(4)
        self.amount_box.setValue(self._order_data["size_stable"])
        self.amount_box.setMaximum(self._order_data["size_stable"])
        self.amount_box.decimalValueChanged.connect(self.on_quantity_change)

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
        self.execute_order_button.clicked.connect(self.on_execute_order)

        self.update_liquidation_price()
        self._toggle_secondary_trigger(False)
        self._update_tp_sl_mode_ui()

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
        self._main_layout.addWidget(self._pair_order_checkbox, 3, 0, 1, 3)
        self._main_layout.addWidget(self._secondary_trigger_label, 4, 0)
        self._main_layout.addWidget(self.secondary_trigger_box, 4, 1)
        self._main_layout.addWidget(self.secondary_trigger_max_button, 4, 2)
        self._main_layout.addWidget(self._amount_label, 5, 0)
        self._main_layout.addWidget(self.amount_box, 5, 1)
        self._main_layout.addWidget(self.amount_max_button, 5, 2)

        self._info_layout.addWidget(self._open_price_label, 0, 0)
        self._info_layout.addWidget(self._open_price_value, 0, 1)
        self._info_layout.addWidget(self._liq_price_label, 1, 0)
        self._info_layout.addWidget(self._liq_price_value, 1, 1)
        self._info_layout.addWidget(self._pnl_label, 2, 0)
        self._info_layout.addWidget(self._pnl_value, 2, 1)
        self._info_frame.setLayout(self._info_layout)
        self._main_layout.addWidget(self._info_frame, 6, 0, 1, 3)

        self._main_layout.addWidget(self.execute_order_button, 7, 0, 1, 3)

        self.setLayout(self._main_layout)

    def update_liquidation_price(self) -> None:
        """Update liquidation price."""
        if self._associated_position is None:
            self._liq_price_value.setText("--")
            return

        liquidation_price = self._exchange.calculate_liquidation_price(self._associated_position)
        minimal_digits = ui_utils.get_minimal_digits(float(liquidation_price), 4)
        self._liq_price_value.setText(
            f"${liquidation_price:,.{minimal_digits}f}",
        )

    def update_pnl(self, price: Decimal) -> None:
        """Update pnl."""
        if self._associated_position is None:
            self._pnl_value.pnl_label.setText("--")
            return

        pnl_details = self._exchange.calculate_pnl(self._associated_position, price)

        self._pnl_value.set_pnl(
            pnl_details["pnl_usd_after_fees"],
            pnl_details["pnl_percentage_after_fees"],
        )
        self._pnl_value.set_tooltip_content(
            pnl_details["pnl_usd_before_fees"],
            pnl_details["funding_fee_usd"],
            pnl_details["opening_fee_usd"],
            pnl_details["closing_fee_usd"] if pnl_details.get("show_closing_fee", True) else None,
            pnl_details["pnl_usd_after_fees"],
            funding_fee_included=pnl_details.get("funding_fee_included_in_pnl", False),
            opening_fee_included=pnl_details.get("opening_fee_included_in_pnl", False),
            labels=(
                pnl_details.get("pnl_label", "PnL"),
                pnl_details.get("net_pnl_label", "PnL After Fees"),
            ),
            show_closing_fee=pnl_details.get("show_closing_fee", True),
            push_tool_tip=False,
        )

    def on_quantity_change(self, new_quantity: Decimal) -> None:
        """Handle quantity change.

        Args:
            new_quantity (float): New quantity.
        """
        # If order is associated with a position, update position size
        if self._associated_position is not None:
            self._associated_position["position_size_stable"] = new_quantity
        self.update_pnl(self.trigger_box.value())

    def _update_tp_sl_mode_ui(self, _button: QtWidgets.QAbstractButton | None = None) -> None:
        """Update labels and paired-order affordance for reduce-only TP/SL flow."""
        is_reduce_only = self._order_data["reduce_only"]
        is_tp_selected = self._selected_order_type() is PerpsTradeType.TRIGGER_TP

        self._pair_order_checkbox.setVisible(is_reduce_only)
        self._pair_order_checkbox.setEnabled(is_reduce_only)
        self._secondary_trigger_label.setVisible(
            is_reduce_only and self._pair_order_checkbox.isChecked()
        )
        self.secondary_trigger_box.setVisible(
            is_reduce_only and self._pair_order_checkbox.isChecked()
        )
        self.secondary_trigger_max_button.setVisible(
            is_reduce_only and self._pair_order_checkbox.isChecked()
        )

        if not is_reduce_only:
            self._trigger_label.setText("Trigger Price:")
            self.execute_order_button.setText("Execute Order")
            return

        if is_tp_selected:
            self._trigger_label.setText("Take Profit Price:")
            self._secondary_trigger_label.setText("Stop Loss Price:")
            self._pair_order_checkbox.setText("Also submit a stop loss")
        else:
            self._trigger_label.setText("Stop Loss Price:")
            self._secondary_trigger_label.setText("Take Profit Price:")
            self._pair_order_checkbox.setText("Also submit a take profit")

        self.execute_order_button.setText("Submit TP/SL")

    def _toggle_secondary_trigger(self, checked: bool) -> None:
        """Show or hide the optional paired TP/SL input."""
        self._secondary_trigger_label.setVisible(checked)
        self.secondary_trigger_box.setVisible(checked)
        self.secondary_trigger_max_button.setVisible(checked)

    def _selected_order_type(self) -> PerpsTradeType:
        """Return currently selected order type."""
        type_button_id = self._type_group.id(self._type_group.checkedButton())
        return PerpsTradeType(type_button_id)

    def _paired_order_type(self) -> PerpsTradeType:
        """Return opposite TP/SL order type for paired submission."""
        if self._selected_order_type() is PerpsTradeType.TRIGGER_TP:
            return PerpsTradeType.TRIGGER_SL
        return PerpsTradeType.TRIGGER_TP

    def _validate_reduce_trigger_price(
        self,
        order_type: PerpsTradeType,
        trigger_price: Decimal,
    ) -> str | None:
        """Validate TP/SL trigger price against the associated position."""
        if trigger_price <= 0:
            return "Trigger price must be greater than zero."

        if self._associated_position is None:
            return None

        open_price = self._associated_position["open_price"]
        is_long = self._associated_position["trade_direction"] is PerpsTradeDirection.LONG

        if order_type is PerpsTradeType.TRIGGER_TP:
            is_valid = trigger_price > open_price if is_long else trigger_price < open_price
            if not is_valid:
                return "Take profit must be on the profitable side of the open price."
            return None

        is_valid = trigger_price < open_price if is_long else trigger_price > open_price
        if not is_valid:
            return "Stop loss must be on the protective side of the open price."
        return None

    def _build_reduce_order_request(self) -> dict[str, object] | None:
        """Build single or paired reduce-order request payload."""
        primary_order_type = self._selected_order_type()
        primary_trigger_price = Decimal(self.trigger_box.value())
        validation_error = self._validate_reduce_trigger_price(
            primary_order_type, primary_trigger_price
        )
        if validation_error is not None:
            QtWidgets.QMessageBox.warning(self, "Invalid Trigger Price", validation_error)
            return None

        secondary_order_type: PerpsTradeType | None = None
        secondary_trigger_price: Decimal | None = None
        if self._pair_order_checkbox.isChecked():
            secondary_order_type = self._paired_order_type()
            secondary_trigger_price = Decimal(self.secondary_trigger_box.value())
            validation_error = self._validate_reduce_trigger_price(
                secondary_order_type,
                secondary_trigger_price,
            )
            if validation_error is not None:
                QtWidgets.QMessageBox.warning(self, "Invalid Trigger Price", validation_error)
                return None

        take_profit_price = (
            primary_trigger_price if primary_order_type is PerpsTradeType.TRIGGER_TP else None
        )
        stop_loss_price = (
            primary_trigger_price if primary_order_type is PerpsTradeType.TRIGGER_SL else None
        )
        if secondary_order_type is PerpsTradeType.TRIGGER_TP:
            take_profit_price = secondary_trigger_price
        if secondary_order_type is PerpsTradeType.TRIGGER_SL:
            stop_loss_price = secondary_trigger_price

        return {
            "pair": self._order_data["pair"],
            "size_stable": Decimal(self.amount_box.value()),
            "trade_direction": self._order_data["trade_direction"],
            "take_profit_price": take_profit_price,
            "stop_loss_price": stop_loss_price,
            "reference_price": primary_trigger_price,
        }

    def set_edit_mode(self, edit_mode: bool) -> None:
        """Set if the widget is editing or creating order.

        Args:
            edit_mode (bool): If true, the widget is in edit mode.
        """
        self.amount_box.setDisabled(edit_mode)
        self.amount_max_button.setDisabled(edit_mode)
        for button in self._type_group.buttons():
            button.setDisabled(edit_mode)
        self._pair_order_checkbox.setDisabled(edit_mode)
        if edit_mode:
            self._pair_order_checkbox.setChecked(False)

    def on_execute_order(self) -> None:
        """Handle execute order button click."""
        if self._order_data["reduce_only"]:
            order_request = self._build_reduce_order_request()
            if order_request is None:
                return
            self.execute_order.emit(order_request)
            self.close()
            return

        # Create order to execture based on current state
        order_type = self._selected_order_type()
        order = OrderData(
            id=self._order_data["id"],
            pair=self._order_data["pair"],
            trade_direction=self._order_data["trade_direction"],
            order_type=order_type,
            trigger_price=Decimal(self.trigger_box.value()),
            size_stable=Decimal(self.amount_box.value()),
            reduce_only=self._order_data["reduce_only"],
        )
        self.execute_order.emit(order)
        self.close()

    def show(self) -> None:
        """Override show method to update button position."""
        super().show()
        self.trigger_box.update_button_position()
        self.secondary_trigger_box.update_button_position()
        self.amount_box.update_button_position()
