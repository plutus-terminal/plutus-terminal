"""Widget to control perps configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from qasync import asyncSlot

from plutus_terminal.ui.widgets.double_spin_button import DoubleSpinBoxWithButton
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


class PerpsConfig(QtWidgets.QWidget):
    """Widget to control perps configuration."""

    _LEVERAGE_PRESET_SIGNAL_NAMES = (
        "leverage_button_1_changed",
        "leverage_button_2_changed",
        "leverage_button_3_changed",
        "leverage_button_4_changed",
        "leverage_button_5_changed",
        "leverage_button_6_changed",
        "leverage_button_7_changed",
    )

    def __init__(
        self,
        ui_controller: UIController,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self._ui_controller = ui_controller
        self._app_config = self._ui_controller.app_config

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.top_bar = TopBar("Trade Settings")
        self._auto_tp_sl_box = QtWidgets.QGroupBox("Auto TP/SL")
        self._auto_tp_sl_box_layout = QtWidgets.QGridLayout()
        self._tp_label = QtWidgets.QLabel("Take Profit:")
        self._tp_spin = DoubleSpinBoxWithButton(button_text="%")
        self._sl_label = QtWidgets.QLabel("Stop Loss:")
        self._sl_spin = DoubleSpinBoxWithButton(button_text="%")
        self._reset_defaults_button = QtWidgets.QPushButton("Reset to Defaults")
        self._tp_sl_update = QtWidgets.QPushButton("Update TP/SL")
        self._advanced_bar = TopBar("Advanced Config")
        self._advanced_box_layout = QtWidgets.QVBoxLayout()
        self._reset_actions_layout = QtWidgets.QHBoxLayout()
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
        self._pair_leverage_hint = QtWidgets.QLabel()
        self._leverage_button_values_box = QtWidgets.QGroupBox("Leverage Buttons")
        self._leverage_button_values_layout = QtWidgets.QGridLayout()
        self._leverage_group = QtWidgets.QButtonGroup()
        self._leverage_layout = QtWidgets.QHBoxLayout()
        self._leverage_button_spins = [QtWidgets.QSpinBox() for _ in range(7)]
        self._leverage_button_update = QtWidgets.QPushButton("Update Leverage Buttons")
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
        self._connect_signals()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.top_bar.icon.setPixmap(QPixmap(":/icons/perps_config_icon"))

        self._tp_spin.setValue(self._app_config.take_profit)
        self._tp_spin.setMinimum(0)
        self._tp_spin.setMaximum(100)
        self._tp_spin.setDecimals(2)

        self._sl_spin.setValue(self._app_config.stop_loss)
        self._sl_spin.setMinimum(0)
        self._sl_spin.setMaximum(100)
        self._sl_spin.setDecimals(2)

        self._reset_defaults_button.setMinimumSize(150, 32)
        self._reset_defaults_button.setProperty("class", "WARNING")
        self._reset_defaults_button.setToolTip(
            "Restore the current account trade settings to the built-in defaults.",
        )
        self._tp_sl_update.setMinimumSize(150, 32)
        self._tp_sl_update.setProperty("class", "APPROVED")

        self._trade_lowest_spin.setMinimum(1)
        self._trade_lowest_spin.setMaximum(100_000_000)
        self._trade_lowest_spin.setValue(self._app_config.trade_value_lowest)

        self._trade_low_spin.setMinimum(1)
        self._trade_low_spin.setMaximum(100_000_000)
        self._trade_low_spin.setValue(self._app_config.trade_value_low)

        self._trade_med_spin.setMinimum(1)
        self._trade_med_spin.setMaximum(100_000_000)
        self._trade_med_spin.setValue(self._app_config.trade_value_medium)

        self._trade_high_spin.setMinimum(1)
        self._trade_high_spin.setMaximum(100_000_000)
        self._trade_high_spin.setValue(self._app_config.trade_value_high)

        self._trade_values_update.setMinimumSize(150, 32)
        self._trade_values_update.setProperty("class", "APPROVED")

        self._rebuild_leverage_buttons()

        self._leverage_spin.setMinimum(1)
        self._leverage_spin.setMaximum(self._ui_controller.current_exchange.max_leverage)
        self._leverage_spin.setValue(self._app_config.leverage)
        self._pair_leverage_hint.setWordWrap(True)
        self._update_pair_leverage_hint()
        for spin_box, leverage_value in zip(
            self._leverage_button_spins,
            self._app_config.leverage_button_values,
            strict=False,
        ):
            spin_box.setMinimum(1)
            spin_box.setMaximum(1000)
            spin_box.setValue(leverage_value)

        self._leverage_set_button.setMinimumSize(150, 32)
        self._leverage_set_button.setProperty("class", "APPROVED")
        self._leverage_set_button.setToolTip(
            "Stores the default leverage. Each pair still uses its own exchange limit.",
        )
        self._leverage_button_update.setMinimumSize(150, 32)
        self._leverage_button_update.setProperty("class", "APPROVED")
        self._leverage_button_update.setToolTip(
            "Preset buttons keep your custom values and always append the live exchange max.",
        )

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._ui_controller.exchange_changed.connect(self._on_new_exchange)
        self._ui_controller.pair_changed.connect(self._on_pair_changed)
        self._reset_defaults_button.clicked.connect(self._reset_defaults)
        self._tp_sl_update.clicked.connect(self._update_tp_sl)
        self._trade_values_update.clicked.connect(self._update_trade_values)
        self._leverage_group.buttonClicked.connect(self._set_leverage_button)
        self._leverage_spin.valueChanged.connect(self._update_leverage_buttons)
        self._leverage_button_update.clicked.connect(self._update_leverage_button_values)
        self._leverage_set_button.clicked.connect(self._set_leverage)

        self._app_config.leverage_changed.connect(self._set_leverage_spin)
        self._app_config.leverage_changed.connect(self._update_leverage_buttons)
        for signal_name in self._LEVERAGE_PRESET_SIGNAL_NAMES:
            getattr(self._app_config, signal_name).connect(self._refresh_leverage_button_controls)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.main_layout.addWidget(self.top_bar)

        self._auto_tp_sl_box_layout.addWidget(self._tp_label, 0, 0)
        self._auto_tp_sl_box_layout.addWidget(self._tp_spin, 0, 1)
        self._auto_tp_sl_box_layout.addWidget(self._sl_label, 1, 0)
        self._auto_tp_sl_box_layout.addWidget(self._sl_spin, 1, 1)
        tp_sl_action_layout = QtWidgets.QHBoxLayout()
        tp_sl_action_layout.addStretch()
        tp_sl_action_layout.addWidget(self._tp_sl_update)
        self._auto_tp_sl_box_layout.addLayout(tp_sl_action_layout, 2, 0, 1, 2)
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
        trade_values_action_layout = QtWidgets.QHBoxLayout()
        trade_values_action_layout.addStretch()
        trade_values_action_layout.addWidget(self._trade_values_update)
        self._trade_values_layout.addLayout(trade_values_action_layout, 4, 0, 1, 2)
        self._trade_values_box.setLayout(self._trade_values_layout)
        self._advanced_box_layout.addWidget(self._trade_values_box)
        for index, spin_box in enumerate(self._leverage_button_spins, start=1):
            self._leverage_button_values_layout.addWidget(
                QtWidgets.QLabel(f"Button {index}:"), index - 1, 0
            )
            self._leverage_button_values_layout.addWidget(spin_box, index - 1, 1)
        leverage_buttons_action_layout = QtWidgets.QHBoxLayout()
        leverage_buttons_action_layout.addStretch()
        leverage_buttons_action_layout.addWidget(self._leverage_button_update)
        self._leverage_button_values_layout.addLayout(leverage_buttons_action_layout, 7, 0, 1, 2)
        self._leverage_button_values_box.setLayout(self._leverage_button_values_layout)
        self._advanced_box_layout.addWidget(self._leverage_button_values_box)
        self._leverage_box_layout.addWidget(self._leverage_label, 0, 0)
        self._leverage_box_layout.addWidget(self._leverage_spin, 0, 1)
        self._leverage_box_layout.addWidget(self._pair_leverage_hint, 1, 0, 1, 2)
        self._leverage_box_layout.addLayout(self._leverage_layout, 2, 0, 1, 2)
        leverage_action_layout = QtWidgets.QHBoxLayout()
        leverage_action_layout.addStretch()
        leverage_action_layout.addWidget(self._leverage_set_button)
        self._leverage_box_layout.addLayout(leverage_action_layout, 3, 0, 1, 2)
        self._leverage_box.setLayout(self._leverage_box_layout)
        self._advanced_box_layout.addWidget(self._leverage_box)
        self._advanced_bar.main_layout.addLayout(self._advanced_box_layout)

        self.main_layout.addWidget(self._advanced_bar)
        self._reset_actions_layout.addStretch()
        self._reset_actions_layout.addWidget(self._reset_defaults_button)
        self.main_layout.addLayout(self._reset_actions_layout)
        self.main_layout.addStretch()

    def refresh_from_config(self) -> None:
        """Reload trade settings from the active saved configuration."""
        self._on_new_exchange()

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
        leverage_button = self._leverage_group.button(int(leverage_value))
        if leverage_button is not None:
            leverage_button.setChecked(True)
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

    def _leverage_button_values(self) -> list[int]:
        """Return normalized leverage button values including the live exchange max."""
        button_values: list[int] = []
        exchange_max_leverage = self._ui_controller.current_exchange.max_leverage
        for leverage_value in [*self._app_config.leverage_button_values, exchange_max_leverage]:
            bounded = max(
                self._ui_controller.current_exchange.min_leverage,
                min(exchange_max_leverage, int(leverage_value)),
            )
            if bounded not in button_values:
                button_values.append(bounded)
        return button_values

    def _rebuild_leverage_buttons(self) -> None:
        """Rebuild leverage preset buttons from config and exchange metadata."""
        checked_id = self._leverage_group.checkedId()
        self._leverage_group.setExclusive(False)
        for button in list(self._leverage_group.buttons()):
            self._leverage_group.removeButton(button)
            self._leverage_layout.removeWidget(button)
            button.deleteLater()
        self._leverage_group.setExclusive(True)

        for value in self._leverage_button_values():
            button = QtWidgets.QRadioButton(str(value))
            self._leverage_group.addButton(button)
            self._leverage_group.setId(button, value)
            self._leverage_layout.addWidget(button)

        fallback_value = (
            self._leverage_spin.value() if self._leverage_spin.value() > 0 else checked_id
        )
        if fallback_value > 0:
            self._update_leverage_buttons(fallback_value)

    def _refresh_leverage_button_controls(self, *_args: object) -> None:
        """Refresh button controls after preset changes."""
        for spin_box, leverage_value in zip(
            self._leverage_button_spins,
            self._app_config.leverage_button_values,
            strict=False,
        ):
            spin_box.blockSignals(True)
            spin_box.setValue(leverage_value)
            spin_box.blockSignals(False)
        self._rebuild_leverage_buttons()

    def _update_leverage_button_values(self) -> None:
        """Persist leverage preset button values."""
        for field_name, spin_box in zip(
            self._app_config.LEVERAGE_BUTTON_FIELDS,
            self._leverage_button_spins,
            strict=False,
        ):
            setattr(self._app_config, field_name, spin_box.value())
        self._refresh_leverage_button_controls()
        Toast.show_message("Leverage buttons updated", type_=ToastType.SUCCESS)

    @asyncSlot()
    async def _set_leverage(self) -> None:
        """Set leverage on exchange.

        Args:
            leverage_value (int): Leverage value to set.
        """
        leverage_value = self._leverage_spin.value()
        await self._ui_controller.set_all_leverage(leverage_value)

    def _update_trade_values(self) -> None:
        """Update trade values."""
        # Blocking signals to avoid mutiple updates
        self._app_config.blockSignals(True)
        self._app_config.trade_value_lowest = self._trade_lowest_spin.value()
        self._app_config.trade_value_low = self._trade_low_spin.value()
        self._app_config.trade_value_medium = self._trade_med_spin.value()
        self._app_config.blockSignals(False)

        self._app_config.trade_value_high = self._trade_high_spin.value()
        Toast.show_message("Trade values updated", type_=ToastType.SUCCESS)

    def _update_tp_sl(self) -> None:
        """Update take profit and stop loss."""
        self._app_config.take_profit = self._tp_spin.value()
        self._app_config.stop_loss = self._sl_spin.value()
        Toast.show_message("TP/SL values updated", type_=ToastType.SUCCESS)

    def _reset_defaults(self) -> None:
        """Reset the current account trade settings to defaults."""
        self._app_config.reset_current_trade_config()
        self._on_new_exchange()
        Toast.show_message("Trade settings reset to defaults", type_=ToastType.SUCCESS)

    def _update_pair_leverage_hint(self) -> None:
        """Render the selected pair leverage cap for exchanges with per-pair limits."""
        current_pair = self._ui_controller.current_pair
        simple_pair = self._ui_controller.current_exchange.format_simple_pair_from_pair(
            current_pair
        )
        max_leverage = self._ui_controller.current_exchange.max_leverage_for_pair(current_pair)
        self._pair_leverage_hint.setText(
            f"Current pair max: {simple_pair} {max_leverage}x. Each pair may use a different cap.",
        )

    def _on_pair_changed(self, _pair: str) -> None:
        """Refresh the leverage hint after the selected pair changes."""
        self._update_pair_leverage_hint()

    def _on_new_exchange(self) -> None:
        """Update widget on new exchange.

        * Update spin box values
        * Update leverage
        """
        self.blockSignals(True)
        self._leverage_spin.setMaximum(self._ui_controller.current_exchange.max_leverage)
        self._rebuild_leverage_buttons()
        # Update spin box values
        for spin, attr in self._spin_config_map.items():
            spin.blockSignals(True)
            spin.setValue(getattr(self._app_config, attr))
            spin.blockSignals(False)

        self._set_leverage_spin(self._app_config.leverage)
        self._update_pair_leverage_hint()
        self._refresh_leverage_button_controls()
        self.blockSignals(False)
