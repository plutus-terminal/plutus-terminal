"""Widget to control terminal configs."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal

from plutus_terminal.ui.widgets.log_viewer import LogViewer
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.core.config import AppConfig


class TerminalConfig(QtWidgets.QWidget):
    """Widget to control terminal configs."""

    def __init__(
        self,
        app_config: AppConfig,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._app_config = app_config

        self._main_layout = QtWidgets.QGridLayout()

        self._top_bar_settings = TopBar("Terminal Settings")

        self._show_images_checkbox = QtWidgets.QCheckBox("Show images on news cards")
        self._show_desktop_news_checkbox = QtWidgets.QCheckBox(
            "Show news as Desktop Popup",
        )
        self._minimize_on_close_checkbox = QtWidgets.QCheckBox(
            "Minimize window to tray on close",
        )
        self._toast_position_label = QtWidgets.QLabel("Toast Notification Position:")
        self._toast_position_combobox = QtWidgets.QComboBox()

        self._top_bar_debugging = TopBar("Debugging")

        self._open_log_label = QtWidgets.QLabel("Open session log:")
        self._open_log_button = QtWidgets.QPushButton("Open Log")
        self._log_viewer = LogViewer()

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self._show_images_checkbox.setChecked(
            self._app_config.get_gui_settings("news_show_images"),  # type: ignore
        )

        self._show_desktop_news_checkbox.setChecked(
            self._app_config.get_gui_settings("news_desktop_notifications"),  # type: ignore
        )

        self._minimize_on_close_checkbox.setChecked(
            self._app_config.get_gui_settings("minimize_to_tray"),  # type: ignore
        )

        for option in ["bottom_left", "bottom_right", "top_left", "top_right"]:
            self._toast_position_combobox.addItem(option.replace("_", " ").title(), option)
        current_index = self._toast_position_combobox.findData(
            self._app_config.get_gui_settings("toast_position"),
            flags=QtCore.Qt.MatchFlag.MatchFixedString,
        )

        self._open_log_button.setMinimumHeight(30)
        self._open_log_button.setToolTip("Open log file")

        self._toast_position_combobox.setCurrentIndex(current_index)

    def _connect_signals(self) -> None:
        """Connect UI Signals."""
        self._show_images_checkbox.toggled.connect(
            partial(self._app_config.set_gui_settings, "news_show_images")
        )
        self._show_desktop_news_checkbox.toggled.connect(
            partial(self._app_config.set_gui_settings, "news_desktop_notifications")
        )
        self._minimize_on_close_checkbox.toggled.connect(
            partial(self._app_config.set_gui_settings, "minimize_to_tray"),
        )

        self._open_log_button.clicked.connect(self._log_viewer.show)
        self._toast_position_combobox.currentIndexChanged.connect(self._set_toast_position)

        self._app_config.news_show_images_changed.connect(self._show_images_checkbox.setChecked)
        self._app_config.news_desktop_notifications_changed.connect(
            self._show_desktop_news_checkbox.setChecked
        )

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._top_bar_settings, 0, 0, 1, 2)
        self._main_layout.addWidget(self._show_images_checkbox, 1, 0, 1, 2)
        self._main_layout.addWidget(self._show_desktop_news_checkbox, 2, 0, 1, 2)
        self._main_layout.addWidget(self._minimize_on_close_checkbox, 3, 0, 1, 2)
        self._main_layout.addWidget(self._toast_position_label, 4, 0)
        self._main_layout.addWidget(self._toast_position_combobox, 4, 1)
        self._main_layout.addWidget(self._top_bar_debugging, 5, 0, 1, 2)
        self._main_layout.addWidget(self._open_log_label, 6, 0)
        self._main_layout.addWidget(self._open_log_button, 6, 1)
        self._main_layout.setRowStretch(self._main_layout.rowCount(), 1)

        self.setLayout(self._main_layout)

    def _set_toast_position(self, index: int) -> None:
        """Set toast position."""
        current_data = self._toast_position_combobox.itemData(index)
        self._app_config.set_gui_settings(
            "toast_position",
            current_data,
        )
        Toast.show_message(
            f"Toast position set to {current_data.replace('_', ' ').title()}",
            type_=ToastType.SUCCESS,
        )
