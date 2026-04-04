"""Widget to control terminal configs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import orjson
from PySide6 import QtCore, QtWidgets

from plutus_terminal.ui.widgets.log_viewer import LogViewer
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from collections.abc import Callable

    from plutus_terminal.core.config import AppConfig


class TerminalConfig(QtWidgets.QWidget):
    """Widget to control terminal configs."""

    def __init__(
        self,
        app_config: AppConfig,
        on_settings_imported: Callable[[], None] | None = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._app_config = app_config
        self._on_settings_imported = on_settings_imported

        self._main_layout = QtWidgets.QGridLayout(self)

        self._top_bar_settings = TopBar("Terminal Settings")

        self._show_images_checkbox = QtWidgets.QCheckBox("Show images on news cards")
        self._show_desktop_news_checkbox = QtWidgets.QCheckBox(
            "Show news as Desktop Popup",
        )
        self._minimize_on_close_checkbox = QtWidgets.QCheckBox(
            "Minimize window to tray on close",
        )
        self._reset_defaults_button = QtWidgets.QPushButton("Reset to Defaults")

        self._top_bar_settings_backup = TopBar("Settings Backup")
        self._backup_hint = QtWidgets.QLabel(
            "Export local trade, terminal, and filter settings without secrets or API keys.",
        )
        self._backup_actions_layout = QtWidgets.QHBoxLayout()
        self._import_settings_button = QtWidgets.QPushButton("Import Local Settings")
        self._export_settings_button = QtWidgets.QPushButton("Export Local Settings")

        self._top_bar_debugging = TopBar("Debugging")
        self._open_log_label = QtWidgets.QLabel("Open session log:")
        self._open_log_button = QtWidgets.QPushButton("Open Log")
        self._log_viewer = LogViewer()

        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._show_images_checkbox.setChecked(
            self._app_config.get_gui_settings("news_show_images"),  # type: ignore[arg-type]
        )
        self._show_desktop_news_checkbox.setChecked(
            self._app_config.get_gui_settings("news_desktop_notifications"),  # type: ignore[arg-type]
        )
        self._minimize_on_close_checkbox.setChecked(
            self._app_config.get_gui_settings("minimize_to_tray"),  # type: ignore[arg-type]
        )

        self._reset_defaults_button.setMinimumSize(150, 32)
        self._reset_defaults_button.setProperty("class", "WARNING")
        self._backup_hint.setWordWrap(True)
        self._backup_hint.setObjectName("subText")

        for button in (
            self._import_settings_button,
            self._export_settings_button,
            self._open_log_button,
        ):
            button.setMinimumHeight(30)

        for button in (self._import_settings_button, self._export_settings_button):
            button.setProperty("class", "APPROVED")
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )

        self._open_log_button.setToolTip("Open the active session log viewer")

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self._show_images_checkbox.toggled.connect(
            lambda checked: self._app_config.set_gui_settings("news_show_images", checked),
        )
        self._show_desktop_news_checkbox.toggled.connect(
            lambda checked: self._app_config.set_gui_settings(
                "news_desktop_notifications",
                checked,
            ),
        )
        self._minimize_on_close_checkbox.toggled.connect(
            lambda checked: self._app_config.set_gui_settings("minimize_to_tray", checked),
        )
        self._reset_defaults_button.clicked.connect(self._reset_defaults)

        self._export_settings_button.clicked.connect(self._export_local_settings)
        self._import_settings_button.clicked.connect(self._import_local_settings)
        self._open_log_button.clicked.connect(self._show_log_viewer)

        self._app_config.news_show_images_changed.connect(self._show_images_checkbox.setChecked)
        self._app_config.news_desktop_notifications_changed.connect(
            self._show_desktop_news_checkbox.setChecked,
        )
        self._app_config.minimize_to_tray_changed.connect(
            self._minimize_on_close_checkbox.setChecked,
        )

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._top_bar_settings, 0, 0, 1, 2)
        self._main_layout.addWidget(self._show_images_checkbox, 1, 0, 1, 2)
        self._main_layout.addWidget(self._show_desktop_news_checkbox, 2, 0, 1, 2)
        self._main_layout.addWidget(self._minimize_on_close_checkbox, 3, 0, 1, 2)
        reset_layout = QtWidgets.QHBoxLayout()
        reset_layout.addStretch()
        reset_layout.addWidget(self._reset_defaults_button)
        self._main_layout.addLayout(reset_layout, 4, 0, 1, 2)

        self._main_layout.addWidget(self._top_bar_settings_backup, 5, 0, 1, 2)
        self._main_layout.addWidget(self._backup_hint, 6, 0, 1, 2)
        self._backup_actions_layout.addWidget(self._import_settings_button, 1)
        self._backup_actions_layout.addWidget(self._export_settings_button, 1)
        self._main_layout.addLayout(self._backup_actions_layout, 7, 0, 1, 2)

        self._main_layout.addWidget(self._top_bar_debugging, 8, 0, 1, 2)
        self._main_layout.addWidget(self._open_log_label, 9, 0)
        self._main_layout.addWidget(self._open_log_button, 9, 1)
        self._main_layout.setColumnStretch(1, 1)
        self._main_layout.setRowStretch(self._main_layout.rowCount(), 1)

    def refresh_from_config(self) -> None:
        """Reload the terminal controls from the saved config state."""
        self._show_images_checkbox.blockSignals(True)
        self._show_desktop_news_checkbox.blockSignals(True)
        self._minimize_on_close_checkbox.blockSignals(True)

        self._show_images_checkbox.setChecked(
            self._app_config.get_gui_settings("news_show_images"),  # type: ignore[arg-type]
        )
        self._show_desktop_news_checkbox.setChecked(
            self._app_config.get_gui_settings("news_desktop_notifications"),  # type: ignore[arg-type]
        )
        self._minimize_on_close_checkbox.setChecked(
            self._app_config.get_gui_settings("minimize_to_tray"),  # type: ignore[arg-type]
        )

        self._show_images_checkbox.blockSignals(False)
        self._show_desktop_news_checkbox.blockSignals(False)
        self._minimize_on_close_checkbox.blockSignals(False)

    def _reset_defaults(self) -> None:
        """Reset terminal settings to defaults."""
        self._app_config.reset_terminal_gui_settings()
        Toast.show_message("Terminal settings reset to defaults", type_=ToastType.SUCCESS)

    def _show_log_viewer(self) -> None:
        """Show the log viewer in front of the config dialog."""
        parent_window = self.window()
        if self._log_viewer.parentWidget() is not parent_window:
            self._log_viewer.setParent(parent_window, self._log_viewer.windowFlags())
        self._log_viewer.open_dialog()

    def _export_local_settings(self) -> None:
        """Export non-secret local settings to a JSON file."""
        export_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Local Settings",
            "plutus-terminal-settings.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if not export_path:
            return

        snapshot = self._app_config.export_settings_snapshot()
        path = Path(export_path)
        path.write_bytes(orjson.dumps(snapshot, option=orjson.OPT_INDENT_2))
        Toast.show_message(
            f"Local settings exported to {path.name}",
            type_=ToastType.SUCCESS,
        )

    def _import_local_settings(self) -> None:
        """Import non-secret local settings from a JSON file."""
        import_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Local Settings",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not import_path:
            return

        path = Path(import_path)
        try:
            snapshot = orjson.loads(path.read_bytes())
        except (FileNotFoundError, OSError, orjson.JSONDecodeError):
            Toast.show_message(
                "Could not import settings from the selected file.",
                type_=ToastType.ERROR,
            )
            return

        warnings = self._app_config.import_settings_snapshot(snapshot)
        if self._on_settings_imported is not None:
            self._on_settings_imported()

        if warnings:
            Toast.show_message(
                "Settings imported with warnings. Review filters and trade values.",
                type_=ToastType.WARNING,
            )
            return

        Toast.show_message(
            f"Local settings imported from {path.name}",
            type_=ToastType.SUCCESS,
        )
