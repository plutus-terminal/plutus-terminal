"""Widget to control toast configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtWidgets

from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.core.config import AppConfig


class ToastConfig(QtWidgets.QWidget):
    """Widget to control toast positions and durations."""

    _POSITION_OPTIONS = ("bottom_left", "bottom_right", "top_left", "top_right")

    def __init__(
        self,
        app_config: AppConfig,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._app_config = app_config

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._top_bar = TopBar("Toast Settings")

        self._message_box = QtWidgets.QGroupBox("Toast Messages")
        self._message_layout = QtWidgets.QGridLayout()
        self._message_position_label = QtWidgets.QLabel("Message Position:")
        self._message_position_combobox = QtWidgets.QComboBox()
        self._message_duration_label = QtWidgets.QLabel("Message Duration:")
        self._message_duration_spin = QtWidgets.QSpinBox()

        self._widget_box = QtWidgets.QGroupBox("Toast Widgets / News")
        self._widget_layout = QtWidgets.QGridLayout()
        self._widget_position_label = QtWidgets.QLabel("Widget Position:")
        self._widget_position_combobox = QtWidgets.QComboBox()
        self._widget_duration_label = QtWidgets.QLabel("Widget Duration:")
        self._widget_duration_spin = QtWidgets.QSpinBox()

        self._hint_label = QtWidgets.QLabel(
            "Messages control short status toasts. Widgets control news popups and other custom toast cards.",
        )
        self._reset_defaults_button = QtWidgets.QPushButton("Reset to Defaults")

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._hint_label.setWordWrap(True)
        self._hint_label.setObjectName("subText")

        for combobox in (self._message_position_combobox, self._widget_position_combobox):
            for option in self._POSITION_OPTIONS:
                combobox.addItem(option.replace("_", " ").title(), option)

        for spin_box in (self._message_duration_spin, self._widget_duration_spin):
            spin_box.setRange(1, 3600)
            spin_box.setSingleStep(1)
            spin_box.setSuffix(" s")

        self._reset_defaults_button.setMinimumSize(150, 32)
        self._reset_defaults_button.setProperty("class", "WARNING")
        self.refresh_from_config()

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self._message_position_combobox.currentIndexChanged.connect(
            self._set_message_position,
        )
        self._widget_position_combobox.currentIndexChanged.connect(
            self._set_widget_position,
        )
        self._message_duration_spin.valueChanged.connect(self._set_message_duration)
        self._widget_duration_spin.valueChanged.connect(self._set_widget_duration)
        self._reset_defaults_button.clicked.connect(self._reset_defaults)

        self._app_config.toast_message_position_changed.connect(self._sync_message_position)
        self._app_config.toast_widget_position_changed.connect(self._sync_widget_position)
        self._app_config.toast_message_duration_changed.connect(self._sync_message_duration)
        self._app_config.toast_widget_duration_changed.connect(self._sync_widget_duration)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._message_layout.addWidget(self._message_position_label, 0, 0)
        self._message_layout.addWidget(self._message_position_combobox, 0, 1)
        self._message_layout.addWidget(self._message_duration_label, 1, 0)
        self._message_layout.addWidget(self._message_duration_spin, 1, 1)
        self._message_box.setLayout(self._message_layout)

        self._widget_layout.addWidget(self._widget_position_label, 0, 0)
        self._widget_layout.addWidget(self._widget_position_combobox, 0, 1)
        self._widget_layout.addWidget(self._widget_duration_label, 1, 0)
        self._widget_layout.addWidget(self._widget_duration_spin, 1, 1)
        self._widget_box.setLayout(self._widget_layout)

        self._main_layout.addWidget(self._top_bar)
        self._main_layout.addWidget(self._hint_label)
        self._main_layout.addWidget(self._message_box)
        self._main_layout.addWidget(self._widget_box)

        action_layout = QtWidgets.QHBoxLayout()
        action_layout.addStretch()
        action_layout.addWidget(self._reset_defaults_button)
        self._main_layout.addLayout(action_layout)
        self._main_layout.addStretch()

    def refresh_from_config(self) -> None:
        """Reload the toast controls from the saved config state."""
        self._sync_message_position(
            str(self._app_config.get_gui_settings("toast_message_position"))
        )
        self._sync_widget_position(str(self._app_config.get_gui_settings("toast_widget_position")))
        self._sync_message_duration(
            int(self._app_config.get_gui_settings("toast_message_duration"))
        )
        self._sync_widget_duration(int(self._app_config.get_gui_settings("toast_widget_duration")))

    def _sync_message_position(self, current_data: str) -> None:
        """Sync the message-position combobox to config changes."""
        self._sync_position_combobox(self._message_position_combobox, current_data)

    def _sync_widget_position(self, current_data: str) -> None:
        """Sync the widget-position combobox to config changes."""
        self._sync_position_combobox(self._widget_position_combobox, current_data)

    def _sync_position_combobox(
        self,
        combobox: QtWidgets.QComboBox,
        current_data: str,
    ) -> None:
        """Sync one toast position combobox."""
        current_index = combobox.findData(current_data, flags=QtCore.Qt.MatchFlag.MatchFixedString)
        if current_index < 0:
            return
        combobox.blockSignals(True)
        combobox.setCurrentIndex(current_index)
        combobox.blockSignals(False)

    def _sync_message_duration(self, duration: int) -> None:
        """Sync the message-duration control to config changes."""
        self._sync_duration_spin(self._message_duration_spin, duration)

    def _sync_widget_duration(self, duration: int) -> None:
        """Sync the widget-duration control to config changes."""
        self._sync_duration_spin(self._widget_duration_spin, duration)

    def _sync_duration_spin(self, spin_box: QtWidgets.QSpinBox, duration: int) -> None:
        """Sync one duration control."""
        spin_box.blockSignals(True)
        spin_box.setValue(duration)
        spin_box.blockSignals(False)

    def _set_message_position(self, index: int) -> None:
        """Persist message-toast position changes."""
        current_data = self._message_position_combobox.itemData(index)
        self._app_config.set_gui_settings("toast_message_position", current_data)
        Toast.show_message("Toast message position updated", type_=ToastType.SUCCESS)

    def _set_widget_position(self, index: int) -> None:
        """Persist widget-toast position changes."""
        current_data = self._widget_position_combobox.itemData(index)
        self._app_config.set_gui_settings("toast_widget_position", current_data)
        Toast.show_message("Toast widget position updated", type_=ToastType.SUCCESS)

    def _set_message_duration(self, duration: int) -> None:
        """Persist message-toast duration changes."""
        self._app_config.set_gui_settings("toast_message_duration", duration)

    def _set_widget_duration(self, duration: int) -> None:
        """Persist widget-toast duration changes."""
        self._app_config.set_gui_settings("toast_widget_duration", duration)

    def _reset_defaults(self) -> None:
        """Reset toast settings to defaults."""
        self._app_config.reset_toast_gui_settings()
        Toast.show_message("Toast settings reset to defaults", type_=ToastType.SUCCESS)
