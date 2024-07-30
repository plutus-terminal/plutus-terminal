"""Widget to control perps configuration."""

from __future__ import annotations

from functools import partial
from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.core.config import CONFIG
from plutus_terminal.ui.widgets.double_spin_button import DoubleSpinBoxWithButton
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar


class PerpsConfig(QtWidgets.QWidget):
    """Widget to control perps configuration."""

    updated_trade_values = Signal()
    leverage_changed = Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.top_bar = TopBar("Perps Config")
        self._auto_tp_sl_box = QtWidgets.QGroupBox("Auto TP/SL")
        self._auto_tp_sl_box_layout = QtWidgets.QGridLayout()
        self._tp_label = QtWidgets.QLabel("Take Profit:")
        self._tp_spin = DoubleSpinBoxWithButton(button_text="%")
        self._sl_label = QtWidgets.QLabel("Stop Loss:")
        self._sl_spin = DoubleSpinBoxWithButton(button_text="%")
        self._tp_sl_update = QtWidgets.QPushButton("Update TP/SL")
        self._advanced_bar = TopBar("Advanced Config")
        self._advanced_box_layout = QtWidgets.QVBoxLayout()
        self._trade_values_box = QtWidgets.QGroupBox("Quick Buy Values")
        self._trade_values_layout = QtWidgets.QGridLayout()
        self._trade_lowest_label = QtWidgets.QLabel("Lowest:")
        self._trade_lowest_spin = QtWidgets.QSpinBox()
        self._trade_low_label = QtWidgets.QLabel("Low:")
        self._trade_low_spin = QtWidgets.QSpinBox()
        self._trade_med_label = QtWidgets.QLabel("Med:")
        self._trade_med_spin = QtWidgets.QSpinBox()
        self._trade_high_label = QtWidgets.QLabel("High:")
        self._trade_high_spin = QtWidgets.QSpinBox()
        self._trade_values_update = QtWidgets.QPushButton("Change Quick Buy Values")
        self._leverage_box = QtWidgets.QGroupBox("Leverage Config")
        self._leverage_box_layout = QtWidgets.QGridLayout()
        self._leverage_label = QtWidgets.QLabel("Leverage:")
        self._leverage_spin = QtWidgets.QSpinBox()
        self._leverage_group = QtWidgets.QButtonGroup()
        self._leverage_layout = QtWidgets.QHBoxLayout()
        self._leverage_set_button = QtWidgets.QPushButton("Set Leverage for All Pairs")

        self._spin_config_map: dict[
            QtWidgets.QSpinBox | QtWidgets.QDoubleSpinBox,
            str,
        ] = {
            self._tp_spin: "take_profit",
            self._sl_spin: "stop_loss",
            self._trade_lowest_spin: "trade_value_lowest",
            self._trade_low_spin: "trade_value_low",
            self._trade_med_spin: "trade_value_medium",
            self._trade_high_spin: "trade_value_high",
        }

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.top_bar.icon.setPixmap(QPixmap(":/icons/perps_config_icon"))

        self._tp_spin.setValue(CONFIG.take_profit)
        self._tp_spin.setMinimum(0)
        self._tp_spin.setMaximum(100)
        self._tp_spin.setDecimals(2)

        self._sl_spin.setValue(CONFIG.stop_loss)
        self._sl_spin.setMinimum(0)
        self._sl_spin.setMaximum(100)
        self._sl_spin.setDecimals(2)

        self._tp_sl_update.setMinimumHeight(35)
        self._tp_sl_update.clicked.connect(self._update_tp_sl)

        self._trade_lowest_spin.setMinimum(1)
        self._trade_lowest_spin.setMaximum(100_000_000)
        self._trade_lowest_spin.setValue(CONFIG.trade_value_lowest)

        self._trade_low_spin.setMinimum(1)
        self._trade_low_spin.setMaximum(100_000_000)
        self._trade_low_spin.setValue(CONFIG.trade_value_low)

        self._trade_med_spin.setMinimum(1)
        self._trade_med_spin.setMaximum(100_000_000)
        self._trade_med_spin.setValue(CONFIG.trade_value_medium)

        self._trade_high_spin.setMinimum(1)
        self._trade_high_spin.setMaximum(100_000_000)
        self._trade_high_spin.setValue(CONFIG.trade_value_high)

        self._trade_values_update.setMinimumHeight(35)
        self._trade_values_update.clicked.connect(self._update_trade_values)

        for value in (2, 5, 10, 20, 25, 50):
            button = QtWidgets.QRadioButton(str(value))
            self._leverage_group.addButton(button)
            self._leverage_group.setId(button, value)
            self._leverage_layout.addWidget(button)
        self._leverage_group.buttonClicked.connect(self._set_leverage_button)

        self._leverage_spin.setMinimum(1)
        self._leverage_spin.setMaximum(50)
        self._leverage_spin.valueChanged.connect(self._update_leverage_buttons)
        self._leverage_spin.setValue(CONFIG.leverage)

        self._leverage_set_button.setMinimumHeight(35)
        self._leverage_set_button.clicked.connect(self._set_leverage)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addWidget(self.top_bar)

        self._auto_tp_sl_box_layout.addWidget(self._tp_label, 0, 0)
        self._auto_tp_sl_box_layout.addWidget(self._tp_spin, 0, 1)
        self._auto_tp_sl_box_layout.addWidget(self._sl_label, 1, 0)
        self._auto_tp_sl_box_layout.addWidget(self._sl_spin, 1, 1)
        self._auto_tp_sl_box_layout.addWidget(self._tp_sl_update, 2, 0, 1, 2)
        self._auto_tp_sl_box.setLayout(self._auto_tp_sl_box_layout)
        self.main_layout.addWidget(self._auto_tp_sl_box)

        self._trade_values_layout.addWidget(self._trade_lowest_label, 0, 0)
        self._trade_values_layout.addWidget(self._trade_lowest_spin, 0, 1)
        self._trade_values_layout.addWidget(self._trade_low_label, 1, 0)
        self._trade_values_layout.addWidget(self._trade_low_spin, 1, 1)
        self._trade_values_layout.addWidget(self._trade_med_label, 2, 0)
        self._trade_values_layout.addWidget(self._trade_med_spin, 2, 1)
        self._trade_values_layout.addWidget(self._trade_high_label, 3, 0)
        self._trade_values_layout.addWidget(self._trade_high_spin, 3, 1)
        self._trade_values_layout.addWidget(self._trade_values_update, 4, 0, 1, 2)
        self._trade_values_box.setLayout(self._trade_values_layout)
        self._advanced_box_layout.addWidget(self._trade_values_box)
        self._leverage_box_layout.addWidget(self._leverage_label, 0, 0)
        self._leverage_box_layout.addWidget(self._leverage_spin, 0, 1)
        self._leverage_box_layout.addLayout(self._leverage_layout, 1, 0, 1, 2)
        self._leverage_box_layout.addWidget(self._leverage_set_button, 2, 0, 1, 2)
        self._leverage_box.setLayout(self._leverage_box_layout)
        self._advanced_box_layout.addWidget(self._leverage_box)
        self._advanced_bar.main_layout.addLayout(self._advanced_box_layout)

        self.main_layout.addWidget(self._advanced_bar)
        self.main_layout.addStretch()

    def _set_leverage_spin(self, leverage_value: int) -> None:
        """Set leverage when spin is changed.

        Update buttons if values matches.

        Args:
            leverage_value (int): Leverage value.
        """
        self._leverage_spin.blockSignals(True)
        self._leverage_spin.setValue(leverage_value)
        self._leverage_spin.blockSignals(False)

    def _update_leverage_buttons(self, leverage_value: int) -> None:
        """Update leverage buttons state based on leverage value."""
        if leverage_value in {2, 5, 10, 20, 25, 50}:
            self._leverage_group.button(int(leverage_value)).setChecked(True)
        else:
            button = self._leverage_group.checkedButton()
            if button:
                self._leverage_group.setExclusive(False)
                button.setChecked(False)
                self._leverage_group.setExclusive(True)

    def _set_leverage_button(self, button: QtWidgets.QRadioButton) -> None:
        """Set leverage spin when button is clicked.

        Args:
            button (QtWidgets.QRadioButton): Leverage button clicked.
        """
        self._set_leverage_spin(self._leverage_group.id(button))

    def _set_leverage(self) -> None:
        """Set leverage on exchange.

        Args:
            leverage_value (int): Leverage value to set.
        """
        leverage_value = self._leverage_spin.value()
        self.leverage_changed.emit(leverage_value)

    def _update_trade_values(self) -> None:
        """Update trade values."""
        CONFIG.trade_value_lowest = self._trade_lowest_spin.value()
        CONFIG.trade_value_low = self._trade_low_spin.value()
        CONFIG.trade_value_medium = self._trade_med_spin.value()
        CONFIG.trade_value_high = self._trade_high_spin.value()
        self.updated_trade_values.emit()

    def _update_tp_sl(self) -> None:
        """Update take profit and stop loss."""
        CONFIG.take_profit = self._tp_spin.value()
        CONFIG.stop_loss = self._sl_spin.value()
        Toast.show_message("TP/SL values updated", type_=ToastType.SUCCESS)

    def on_new_account(self) -> None:
        """Update info based on new account."""
        self.blockSignals(True)
        # Update spin box values
        for spin, attr in self._spin_config_map.items():
            spin.blockSignals(True)
            spin.setValue(getattr(CONFIG, attr))
            spin.blockSignals(False)

        self._set_leverage_spin(CONFIG.leverage)
        self.blockSignals(False)
