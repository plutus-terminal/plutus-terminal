"""Dialog to manage configurations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap

from plutus_terminal.ui.widgets.config.account_config import AccountConfig
from plutus_terminal.ui.widgets.config.news_config import NewsFiltersConfig, NewsSourceConfig
from plutus_terminal.ui.widgets.config.perps_config import PerpsConfig
from plutus_terminal.ui.widgets.config.terminal_config import TerminalConfig
from plutus_terminal.ui.widgets.config.toast_config import ToastConfig

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController


class ConfigDialog(QtWidgets.QDialog):
    """Config dialog."""

    _DEFAULT_OPEN_SIZE = QtCore.QSize(1100, 900)

    def __init__(
        self,
        ui_controller: UIController,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize dialog."""
        super().__init__(parent)

        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        self._tab_widget = QtWidgets.QTabWidget()
        self.persp_config = PerpsConfig(ui_controller, parent=self)
        self.news_source_config = NewsSourceConfig(ui_controller, parent=self)
        self.news_filters_config = NewsFiltersConfig(ui_controller, parent=self)
        self.account_config = AccountConfig(
            ui_controller.pass_guard,
            ui_controller.app_config,
            parent=self,
        )
        self.terminal_config = TerminalConfig(
            ui_controller.app_config,
            on_settings_imported=ui_controller.update_news_filters,
            parent=self,
        )
        self.toast_config = ToastConfig(ui_controller.app_config, parent=self)

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self.setWindowTitle("Plutus Terminal - Configuration")
        self.setWindowIcon(QPixmap(":/icons/plutus_icon"))
        self.setModal(False)
        self.setMinimumSize(800, 800)

        self._tab_widget.addTab(self.persp_config, "Trade")

        self._tab_widget.addTab(self.news_source_config, "News APIs")

        self._tab_widget.addTab(self.news_filters_config, "News Filters")

        self._tab_widget.addTab(self.account_config, "Account")

        self._tab_widget.addTab(self.toast_config, "Toasts")

        self._tab_widget.addTab(self.terminal_config, "Terminal")

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._tab_widget)
        self.setLayout(self._main_layout)

    def _target_open_size(self) -> QtCore.QSize:
        """Return the minimum practical size for the current config content."""
        return (
            self._DEFAULT_OPEN_SIZE.expandedTo(self.minimumSize())
            .expandedTo(self.sizeHint())
            .expandedTo(self._tab_widget.sizeHint())
        )

    def _ensure_open_size(self) -> None:
        """Grow the dialog so it opens large enough for the config tabs."""
        self.ensurePolished()
        self.resize(self.size().expandedTo(self._target_open_size()))

    def refresh_from_config(self) -> None:
        """Reload all tab widgets from the current saved settings."""
        for widget in (
            self.persp_config,
            self.news_source_config,
            self.news_filters_config,
            self.account_config,
            self.terminal_config,
            self.toast_config,
        ):
            refresh = getattr(widget, "refresh_from_config", None)
            if callable(refresh):
                refresh()

    def open_dialog(self) -> None:
        """Show the dialog and bring it to the foreground."""
        self.refresh_from_config()
        self._ensure_open_size()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Refresh visible tab state whenever the dialog is shown."""
        self.refresh_from_config()
        super().showEvent(event)
        self._ensure_open_size()
