"""Widget to buy options with strategy."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qasync import asyncSlot

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.types_ import (
    OptionsDirection,
    OptionsDuration,
    OptionsRisk,
)
from plutus_terminal.ui.widgets.options_table import OptionsTableModel, OptionsTableView

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase


class OptionsWidget(QtWidgets.QWidget):
    """Widget to buy options with strategy."""

    def __init__(
        self,
        exchange: ExchangeBase,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self._exchange = exchange
        self._stop_update = asyncio.Event()
        self._update_task: Optional[asyncio.Task] = None

        self.main_layout = QtWidgets.QGridLayout(self)

        self._top_bar_layout = QtWidgets.QHBoxLayout()
        self._top_bar_icon = QtWidgets.QLabel()
        self._top_bar_title = QtWidgets.QLabel("Options Strategy")
        self._top_bar_preview = QtWidgets.QRadioButton()
        self._top_bar_line = QtWidgets.QFrame()

        self.token_label = QtWidgets.QLabel("Token:")
        self.token_combo = QtWidgets.QComboBox()
        self.amount_label = QtWidgets.QLabel("Amount to buy:")
        self.amount_spin = QtWidgets.QDoubleSpinBox()
        self.rate_min_label = QtWidgets.QLabel("Rate Min:")
        self.rate_min_spin = QtWidgets.QDoubleSpinBox()
        self.available_min_label = QtWidgets.QLabel("Available Min:")
        self.available_min_spin = QtWidgets.QDoubleSpinBox()
        self.percent_min_label = QtWidgets.QLabel("Percent Min:")
        self.percent_min_group = QtWidgets.QButtonGroup()
        self.percent_min_layout = QtWidgets.QHBoxLayout()
        self.percent_max_label = QtWidgets.QLabel("Percent Max:")
        self.percent_max_group = QtWidgets.QButtonGroup()
        self.percent_max_layout = QtWidgets.QHBoxLayout()
        self.duration_min_label = QtWidgets.QLabel("Duration Min:")
        self.duration_min_group = QtWidgets.QButtonGroup()
        self.duration_min_layout = QtWidgets.QHBoxLayout()
        self.duration_max_label = QtWidgets.QLabel("Duration Max:")
        self.duration_max_group = QtWidgets.QButtonGroup()
        self.duration_max_layout = QtWidgets.QHBoxLayout()
        self.risk_label = QtWidgets.QLabel("Risk:")
        self.risk_group = QtWidgets.QButtonGroup()
        self.risk_layout = QtWidgets.QHBoxLayout()

        self.buy_up_button = QtWidgets.QPushButton("Buy Up")
        self.buy_down_button = QtWidgets.QPushButton("Buy Down")

        self._tab_table = QtWidgets.QTabWidget()
        self._long_table_model = OptionsTableModel()
        self._long_table_view = OptionsTableView()
        self._long_posible_buy = QtWidgets.QLabel()
        self._short_table_model = OptionsTableModel()
        self._short_table_view = OptionsTableView()
        self._short_posible_buy = QtWidgets.QLabel()

        self._percent_text = ["0%", "0.10%", "0.25%", "0.50%", "1%", "3%", "5%"]

        self._spin_config_map = {
            self.amount_spin: "options_amount",
            self.rate_min_spin: "options_rate_min",
            self.available_min_spin: "options_available_min",
        }

        self._button_grp_config_map = {
            self.percent_min_group: "options_percent_min",
            self.percent_max_group: "options_percent_max",
            self.duration_min_group: "options_duration_min",
            self.duration_max_group: "options_duration_max",
            self.risk_group: "options_risk",
        }

        self._setup_widgets()
        self._setup_layout()
        self._setup_for_has_options()

    def _setup_widgets(self) -> None:  # noqa: C901, PLR0915
        """Create widgets."""
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )

        self._top_bar_icon.setPixmap(QPixmap(":icons/options_icon"))
        self._top_bar_icon.setMinimumHeight(35)
        self._top_bar_title.setObjectName("title")
        self._top_bar_title.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._top_bar_title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        self._top_bar_preview.setIcon(QPixmap(":/icons/preview_icon"))
        self._top_bar_preview.setChecked(
            CONFIG.get_gui_settings("options_show_preview"),
        )
        self._top_bar_preview.setToolTip(
            "Show options that will be bought with current strategy.",
        )
        self._top_bar_preview.toggled.connect(self.show_preview_toggled)

        self._top_bar_line.setObjectName("divisor")
        self._top_bar_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self._top_bar_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

        self.amount_spin.setMaximum(1_000_000_000)
        self.amount_spin.setMinimum(1)
        self.amount_spin.setValue(CONFIG.options_amount)
        self.amount_spin.valueChanged.connect(
            partial(setattr, CONFIG, "options_amount"),
        )

        self.rate_min_spin.setMaximum(100)
        self.rate_min_spin.setMinimum(0.01)
        self.rate_min_spin.setSingleStep(0.01)
        self.rate_min_spin.setValue(CONFIG.options_rate_min)
        self.rate_min_spin.valueChanged.connect(
            partial(setattr, CONFIG, "options_rate_min"),
        )

        self.available_min_spin.setMaximum(100_000_000_000)
        self.available_min_spin.setMinimum(2.5)
        self.available_min_spin.setValue(CONFIG.options_available_min)
        self.available_min_spin.valueChanged.connect(
            partial(setattr, CONFIG, "options_available_min"),
        )

        for percent in self._percent_text:
            button = QtWidgets.QRadioButton(percent)
            if percent == CONFIG.options_percent_min:
                button.setChecked(True)
            self.percent_min_group.addButton(button)
            self.percent_min_layout.addWidget(button)

        self.percent_min_group.buttonClicked.connect(
            partial(self._set_config_property, "options_percent_min"),
        )

        for percent in self._percent_text:
            button = QtWidgets.QRadioButton(percent)
            if percent == CONFIG.options_percent_max:
                button.setChecked(True)
            self.percent_max_group.addButton(button)
            self.percent_max_layout.addWidget(button)

        self.percent_max_group.buttonClicked.connect(
            partial(self._set_config_property, "options_percent_max"),
        )

        for risk in OptionsDuration:
            button = QtWidgets.QRadioButton(risk.name)
            if risk == CONFIG.options_duration_min:
                button.setChecked(True)
            self.duration_min_group.addButton(button)
            self.duration_min_layout.addWidget(button)

        self.duration_min_group.buttonClicked.connect(
            partial(
                self._set_config_property_enum,
                "options_duration_min",
                OptionsDuration,
            ),
        )

        for duration in OptionsDuration:
            button_duration = QtWidgets.QRadioButton(duration.name)
            if duration == CONFIG.options_duration_max:
                button_duration.setChecked(True)
            self.duration_max_group.addButton(button_duration)
            self.duration_max_layout.addWidget(button_duration)

        self.duration_max_group.buttonClicked.connect(
            partial(
                self._set_config_property_enum,
                "options_duration_max",
                OptionsDuration,
            ),
        )

        for risk in OptionsRisk:
            button_risk = QtWidgets.QRadioButton(risk.name)
            if risk.name == CONFIG.options_risk.name:
                button_risk.setChecked(True)
            self.risk_group.addButton(button_risk)
            self.risk_layout.addWidget(button_risk)

        self.risk_group.buttonClicked.connect(
            partial(self._set_config_property_enum, "options_risk", OptionsRisk),
        )

        self.buy_up_button.setProperty("class", "LONG")
        self.buy_up_button.setMinimumHeight(35)
        self.buy_up_button.clicked.connect(
            partial(self._buy_options, OptionsDirection.UP),
        )

        self.buy_down_button.setProperty("class", "SHORT")
        self.buy_down_button.setMinimumHeight(35)
        self.buy_down_button.clicked.connect(
            partial(self._buy_options, OptionsDirection.DOWN),
        )

        self._long_posible_buy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._short_posible_buy.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._tab_table.setVisible(CONFIG.get_gui_settings("options_show_preview"))

        self._long_table_view.setModel(self._long_table_model)
        self._short_table_view.setModel(self._short_table_model)

    def _setup_for_has_options(self) -> None:
        """Configure widget for has options enabled."""
        if self._exchange.has_options():
            avilable_pairs = self._exchange.options.fetch_available_pairs()
            self.buy_up_button.setEnabled(True)
            self.buy_down_button.setEnabled(True)
            self._top_bar_preview.setEnabled(True)
        else:
            avilable_pairs = []
            self.buy_up_button.setEnabled(False)
            self.buy_down_button.setEnabled(False)
            self._top_bar_preview.setEnabled(False)
        self.token_combo.addItems(avilable_pairs)

        # Start update task to show preivew if enabled
        if self._exchange.has_options() and CONFIG.get_gui_settings(
            "options_show_preview",
        ):  # type: ignore
            self._update_task = asyncio.create_task(self.update_previews())

    @asyncSlot()
    async def _set_config_property(
        self,
        property_name: str,
        button: QtWidgets.QRadioButton,
    ) -> None:
        """Set property on config."""
        setattr(CONFIG, property_name, button.text())
        await self._update_previews()

    @asyncSlot()
    async def _set_config_property_enum(
        self,
        property_name: str,
        enum: type[OptionsRisk | OptionsDuration],
        button: QtWidgets.QRadioButton,
    ) -> None:
        """Set property on config."""
        setattr(CONFIG, property_name, enum[button.text()].value)
        await self._update_previews()

    @asyncSlot()
    async def _buy_options(self, direction: OptionsDirection) -> None:
        """Buy options."""
        await self._exchange.buy_options_with_strategy(
            direction,
            Decimal(self.amount_spin.value()),
            self.token_combo.currentText(),
        )

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._top_bar_layout.addWidget(self._top_bar_icon)
        self._top_bar_layout.addWidget(self._top_bar_title)
        self._top_bar_layout.addStretch()
        self._top_bar_layout.addWidget(self._top_bar_preview)
        self.main_layout.addLayout(self._top_bar_layout, 0, 0, 1, 2)
        self.main_layout.addWidget(self._top_bar_line, 1, 0, 1, 2)
        self.main_layout.addWidget(self.token_label, 2, 0)
        self.main_layout.addWidget(self.token_combo, 2, 1)
        self.main_layout.addWidget(self.amount_label, 3, 0)
        self.main_layout.addWidget(self.amount_spin, 3, 1)
        self.main_layout.addWidget(self.rate_min_label, 4, 0)
        self.main_layout.addWidget(self.rate_min_spin, 4, 1)
        self.main_layout.addWidget(self.available_min_label, 5, 0)
        self.main_layout.addWidget(self.available_min_spin, 5, 1)
        self.main_layout.addWidget(self.percent_min_label, 6, 0, 1, 2)
        self.main_layout.addLayout(self.percent_min_layout, 7, 0, 1, 2)
        self.main_layout.addWidget(self.percent_max_label, 8, 0, 1, 2)
        self.main_layout.addLayout(self.percent_max_layout, 9, 0, 1, 2)
        self.main_layout.addWidget(self.duration_min_label, 10, 0, 1, 2)
        self.main_layout.addLayout(self.duration_min_layout, 11, 0, 1, 2)
        self.main_layout.addWidget(self.duration_max_label, 12, 0, 1, 2)
        self.main_layout.addLayout(self.duration_max_layout, 13, 0, 1, 2)
        self.main_layout.addWidget(self.risk_label, 14, 0, 1, 2)
        self.main_layout.addLayout(self.risk_layout, 15, 0, 1, 2)
        self.main_layout.addWidget(self.buy_up_button, 16, 0)
        self.main_layout.addWidget(self.buy_down_button, 16, 1)

        long_tab_layout = QtWidgets.QVBoxLayout()
        long_tab_layout.addWidget(self._long_table_view)
        long_tab_layout.addWidget(self._long_posible_buy)
        long_tab_widget = QtWidgets.QWidget()
        long_tab_widget.setContentsMargins(0, 0, 0, 0)
        long_tab_widget.setLayout(long_tab_layout)
        self._tab_table.addTab(long_tab_widget, "Buy Up Preview")

        short_tab_layout = QtWidgets.QVBoxLayout()
        short_tab_layout.addWidget(self._short_table_view)
        short_tab_layout.addWidget(self._short_posible_buy)
        short_tab_widget = QtWidgets.QWidget()
        short_tab_widget.setContentsMargins(0, 0, 0, 0)
        short_tab_widget.setLayout(short_tab_layout)
        self._tab_table.addTab(short_tab_widget, "Buy Down Preview")

        self.main_layout.addWidget(self._tab_table, 17, 0, 1, 2)
        self.main_layout.setRowStretch(18, 1)

    @asyncSlot()
    async def show_preview_toggled(self, checked: bool) -> None:
        """Show preview."""
        CONFIG.set_gui_settings("options_show_preview", checked)
        self._tab_table.setVisible(checked)
        if checked:
            if self._update_task is not None:
                await self._update_task
            self._stop_update.clear()
            self._update_task = asyncio.create_task(self.update_previews())
        else:
            self._stop_update.set()
            if self._update_task is not None:
                await self._update_task

    async def update_previews(self) -> None:
        """Infinite async loop to update options previews each 5 seconds."""
        while not self._stop_update.is_set():
            await self._update_previews()
            await asyncio.sleep(5)

    async def _update_previews(self) -> None:
        """Update strategy previews based on current values."""
        up_data = await self._exchange.options.filter_with_strategy(
            OptionsDirection.UP,
            Decimal(self.amount_spin.value()),
            self.token_combo.currentText(),
        )
        self._long_table_model.update_data(up_data)
        if up_data.empty:
            total_available = 0.0
        else:
            total_available = up_data["available"].sum() / 10**6
            if total_available > self.amount_spin.value():
                total_available = self.amount_spin.value()
        self._long_posible_buy.setText(
            f"<u><b>${total_available:,.2f}</b> "
            "to be bought in "
            f"<b>{up_data.shape[0]}</b> different options</u>",
        )
        down_data = await self._exchange.options.filter_with_strategy(
            OptionsDirection.DOWN,
            Decimal(self.amount_spin.value()),
            self.token_combo.currentText(),
        )
        self._short_table_model.update_data(down_data)
        if down_data.empty:
            total_available = 0
        else:
            total_available = down_data["available"].sum() / 10**6
            if total_available > self.amount_spin.value():
                total_available = self.amount_spin.value()
        self._short_posible_buy.setText(
            f"<u><b>${total_available:,.2f}</b> "
            "to be bought in "
            f"<b>{down_data.shape[0]}</b> different options</u>",
        )

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._stop_update.set()
        self._exchange = new_exchange
        self._setup_for_has_options()

    def on_new_account(self) -> None:
        """Update widgets  on new account."""
        # Update spin box values
        for spin, attr in self._spin_config_map.items():
            spin.blockSignals(True)
            spin.setValue(getattr(CONFIG, attr))
            spin.blockSignals(False)

        for button_grp, attr in self._button_grp_config_map.items():
            button_grp.blockSignals(True)
            for button in button_grp.buttons():
                if button.text() == getattr(CONFIG, attr):
                    button.setChecked(True)
            button_grp.blockSignals(False)
