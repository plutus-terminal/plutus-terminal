"""Widget to control terminal configs."""

from __future__ import annotations

from typing import Optional

import orjson
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal

from plutus_terminal.core.config import CONFIG
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar


class TerminalConfig(QtWidgets.QWidget):
    """Widget to control terminal configs."""

    show_images_toggled = Signal(bool)
    desktop_notifications_toggled = Signal(bool)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)

        self._main_layout = QtWidgets.QGridLayout()

        self._top_bar = TopBar("Terminal Settings")

        self._show_images_checkbox = QtWidgets.QCheckBox("Show images on news cards")
        self._show_desktop_news_checkbox = QtWidgets.QCheckBox(
            "Show news as Desktop Popup",
        )
        self._minimize_on_close_checkbox = QtWidgets.QCheckBox(
            "Minimize window to tray on close",
        )
        self._toast_position_label = QtWidgets.QLabel("Toast Notification Position:")
        self._toast_position_combobox = QtWidgets.QComboBox()

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self._show_images_checkbox.setChecked(
            CONFIG.get_gui_settings("news_show_images"),
        )
        self._show_images_checkbox.toggled.connect(self.show_images_toggled)

        self._show_desktop_news_checkbox.setChecked(
            CONFIG.get_gui_settings("news_desktop_notifications"),
        )
        self._show_desktop_news_checkbox.toggled.connect(
            self.desktop_notifications_toggled,
        )

        self._minimize_on_close_checkbox.setChecked(
            CONFIG.get_gui_settings("minimize_to_tray"),
        )
        self._minimize_on_close_checkbox.toggled.connect(
            lambda value: CONFIG.set_gui_settings("minimize_to_tray", value),
        )

        for option in ["bottom_left", "bottom_right", "top_left", "top_right"]:
            self._toast_position_combobox.addItem(option.replace("_", " ").title(), option)
        current_index = self._toast_position_combobox.findData(
            CONFIG.get_gui_settings("toast_position"),
            flags=QtCore.Qt.MatchFlag.MatchFixedString,
        )
        self._toast_position_combobox.setCurrentIndex(current_index)
        self._toast_position_combobox.currentIndexChanged.connect(self._set_toast_position)

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._top_bar, 0, 0, 1, 2)
        self._main_layout.addWidget(self._show_images_checkbox, 1, 0, 1, 2)
        self._main_layout.addWidget(self._show_desktop_news_checkbox, 2, 0, 1, 2)
        self._main_layout.addWidget(self._minimize_on_close_checkbox, 3, 0, 1, 2)
        self._main_layout.addWidget(self._toast_position_label, 4, 0)
        self._main_layout.addWidget(self._toast_position_combobox, 4, 1)
        self._main_layout.setRowStretch(self._main_layout.rowCount(), 1)

        self.setLayout(self._main_layout)

    def _set_toast_position(self, index: int) -> None:
        """Set toast position."""
        current_data = self._toast_position_combobox.itemData(index)
        CONFIG.set_gui_settings(
            "toast_position",
            current_data,
        )
        Toast.show_message(
            f"Toast position set to {current_data.replace('_', ' ').title()}",
            type_=ToastType.SUCCESS,
        )
