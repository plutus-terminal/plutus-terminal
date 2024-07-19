"""Dialog to manage orders."""

from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from plutus_terminal.core.exchange.types import (
    OrderData,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui.widgets.extra import DoubleSpinBoxWithButton
from plutus_terminal.ui.widgets.top_bar_widget import TopBar


class ManageOrder(QtWidgets.QDialog):
    """Dialog to manage orders."""

    def __init__(
        self,
        order_data: OrderData,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize dialog."""
        super().__init__(parent)
        self._order_data = order_data

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
        self._pnl_label = QtWidgets.QLabel("PnL:")
        self._pnl_value = QtWidgets.QLabel("--")
        self._pnl_after_fee_label = QtWidgets.QLabel("PnL After Fee:")
        self._pnl_after_fee_value = QtWidgets.QLabel("--")

        self._trigger_label = QtWidgets.QLabel("Trigger Price:")
        self.trigger_box = DoubleSpinBoxWithButton(button_text="USD")

        self._quantity_label = QtWidgets.QLabel("Quantity:")
        self.quantity_box = QtWidgets.QDoubleSpinBox()

        self.execute_order_button = QtWidgets.QPushButton("Execute Order")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setModal(False)
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setWindowTitle("Manage Order")
        self.setMinimumSize(400, 300)

        title_color = (
            "color: rgb(255, 100, 100);"
            if self._order_data["trade_direction"].value == PerpsTradeDirection.SHORT.value
            else "color: rgb(100, 255, 100);"
        )
        self.top_bar.title.setText(
            f"{self._order_data['pair']} | "
            f"<span style='{title_color};'>{self._order_data['trade_direction'].name}</span>",
        )

        self._open_price_value.setText(str(self._order_data["trigger_price"]))
        self._open_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._liq_price_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._type_group.addButton(self.limit_button, PerpsTradeType.LIMIT.value)
        self._type_group.addButton(self.tp_button, PerpsTradeType.TRIGGER_TP.value)
        self._type_group.addButton(self.sl_button, PerpsTradeType.TRIGGER_SL.value)
        self._type_group.button(self._order_data["order_type"].value).click()
        self._type_group.buttonClicked.connect(self._on_type_change)

        self._type_group.button(PerpsTradeType.LIMIT.value).setDisabled(
            self._order_data["reduce_only"],
        )

        self.trigger_box.setValue(float(self._order_data["trigger_price"]))
        self.trigger_box.button.clicked.connect(
            lambda: self.trigger_box.setValue(float(self._order_data["trigger_price"])),
        )

        self.quantity_box.setValue(float(self._order_data["size_stable"]))

        self._info_frame.setObjectName("newsFrameQuote")
        self._info_frame.setVisible(self._order_data["reduce_only"])
        self._pnl_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._pnl_after_fee_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.execute_order_button.setMinimumHeight(30)

    def _setup_layout(self) -> None:
        """Configure layouts."""
        self._type_group_layout.addWidget(self.limit_button)
        self._type_group_layout.addWidget(self.tp_button)
        self._type_group_layout.addWidget(self.sl_button)

        self._main_layout.addWidget(self.top_bar, 0, 0, 1, 2)
        self._main_layout.addLayout(self._type_group_layout, 1, 0, 1, 2)
        self._main_layout.addWidget(self._trigger_label, 2, 0)
        self._main_layout.addWidget(self.trigger_box, 2, 1)
        self._main_layout.addWidget(self._quantity_label, 3, 0)
        self._main_layout.addWidget(self.quantity_box, 3, 1)

        self._info_layout.addWidget(self._open_price_label, 0, 0)
        self._info_layout.addWidget(self._open_price_value, 0, 1)
        self._info_layout.addWidget(self._liq_price_label, 1, 0)
        self._info_layout.addWidget(self._liq_price_value, 1, 1)
        self._info_layout.addWidget(self._pnl_label, 2, 0)
        self._info_layout.addWidget(self._pnl_value, 2, 1)
        self._info_layout.addWidget(self._pnl_after_fee_label, 3, 0)
        self._info_layout.addWidget(self._pnl_after_fee_value, 3, 1)
        self._info_frame.setLayout(self._info_layout)
        self._main_layout.addWidget(self._info_frame, 4, 0, 1, 2)

        self._main_layout.addWidget(self.execute_order_button, 5, 0, 1, 2)

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

    def show(self) -> None:
        """Override show method to update button position."""
        super().show()
        self.trigger_box.update_button_position()
