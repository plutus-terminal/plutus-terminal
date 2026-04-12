"""Widgets to control news configuration."""

from __future__ import annotations

from functools import partial
import logging
from typing import TYPE_CHECKING, Optional, cast

import keyring
from keyring.errors import PasswordDeleteError
import orjson
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtMultimedia import QSoundEffect
from qasync import asyncSlot

from plutus_terminal.core import keyring_manager
from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.db.models import UserFilter
from plutus_terminal.core.exceptions import KeyringPasswordNotFoundError
from plutus_terminal.core.news.filter._actions import FILTER_ACTIONS_MAP
from plutus_terminal.core.news.filter.types import ActionType, FilterType
from plutus_terminal.core.news.phoenix_news import PhoenixNews
from plutus_terminal.core.news.synoptic_news import SynopticNews
from plutus_terminal.core.news.tree_news import TreeNews
from plutus_terminal.ui.ui_utils import list_resources_from_prefix
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController

LOGGER = logging.getLogger(__name__)


class NewsSourceConfig(QtWidgets.QWidget):
    """Widget to control news API configuration."""

    def __init__(
        self, ui_controller: UIController, parent: QtWidgets.QWidget | None = None
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._ui_controller = ui_controller
        self._pass_guard = self._ui_controller.pass_guard

        self._main_layout = QtWidgets.QVBoxLayout(self)

        self._news_source_bar = TopBar("News Source API Keys")

        self._tree_box = QtWidgets.QGroupBox("TreeOfAlpha API Key")
        self._tree_box_layout = QtWidgets.QVBoxLayout()
        self._tree_text_label = QtWidgets.QLabel()
        self._tree_input = QtWidgets.QLineEdit()
        self._tree_button = QtWidgets.QPushButton("Update API Key")
        self._tree_password_button = QtWidgets.QPushButton()
        self._tree_validation_label = QtWidgets.QLabel()

        self._phoenix_box = QtWidgets.QGroupBox("Phoenix API Key")
        self._phoenix_box_layout = QtWidgets.QVBoxLayout()
        self._phoenix_text_label = QtWidgets.QLabel()
        self._phoenix_input = QtWidgets.QLineEdit()
        self._phoenix_button = QtWidgets.QPushButton("Update API Key")
        self._phoenix_password_button = QtWidgets.QPushButton()
        self._phoenix_validation_label = QtWidgets.QLabel()

        self._synoptic_box = QtWidgets.QGroupBox("Synoptic API Key")
        self._synoptic_box_layout = QtWidgets.QVBoxLayout()
        self._synoptic_text_label = QtWidgets.QLabel()
        self._synoptic_input = QtWidgets.QLineEdit()
        self._synoptic_button = QtWidgets.QPushButton("Update API Key")
        self._synoptic_password_button = QtWidgets.QPushButton()
        self._synoptic_validation_label = QtWidgets.QLabel()

        self._reset_defaults_button = QtWidgets.QPushButton("Reset to Defaults")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        self._tree_text_label.setWordWrap(True)
        self._tree_text_label.setText(
            """Add your TreeOfAlpha API key below if you are a paid subscriber.<br>"""
            """To get your API key, go to """
            """<a href="https://news.treeofalpha.com/api/api_key" """
            """style="color:rgb(80, 210, 180)">"""
            """https://news.treeofalpha.com/api/api_key</a>""",
        )
        self._tree_text_label.setOpenExternalLinks(True)
        self._setup_api_widgets(
            line_edit=self._tree_input,
            button=self._tree_button,
            password_button=self._tree_password_button,
            validation_label=self._tree_validation_label,
            service_name=TreeNews.NEWS_SERVICE_NAME,
        )

        self._phoenix_text_label.setWordWrap(True)
        self._phoenix_text_label.setText(
            """Add your PhoenixNews API key below if you are a paid subscriber.<br>"""
            """To get your API key, go to """
            """<a href="https://phoenixnews.io" style="color:rgb(80, 210, 180)">"""
            """https://phoenixnews.io</a>""",
        )
        self._phoenix_text_label.setOpenExternalLinks(True)
        self._setup_api_widgets(
            line_edit=self._phoenix_input,
            button=self._phoenix_button,
            password_button=self._phoenix_password_button,
            validation_label=self._phoenix_validation_label,
            service_name=PhoenixNews.NEWS_SERVICE_NAME,
        )

        self._synoptic_text_label.setWordWrap(True)
        self._synoptic_text_label.setText(
            """Add your Synoptic API key below.<br>"""
            """To get your API key, go to """
            """<a href="https://synoptic.com/p/settings/api-keys" """
            """style="color:rgb(80, 210, 180)">"""
            """https://synoptic.com/p/settings/api-keys</a>""",
        )
        self._synoptic_text_label.setOpenExternalLinks(True)
        self._setup_api_widgets(
            line_edit=self._synoptic_input,
            button=self._synoptic_button,
            password_button=self._synoptic_password_button,
            validation_label=self._synoptic_validation_label,
            service_name=SynopticNews.NEWS_SERVICE_NAME,
        )

        self._load_saved_api_key(
            TreeNews.NEWS_SERVICE_NAME,
            self._tree_input,
            "Enter your TreeOfAlpha API key here...",
        )
        self._load_saved_api_key(
            PhoenixNews.NEWS_SERVICE_NAME,
            self._phoenix_input,
            "Enter your Phoenix API key here...",
        )
        self._load_saved_api_key(
            SynopticNews.NEWS_SERVICE_NAME,
            self._synoptic_input,
            "Enter your Synoptic API key here...",
        )

        self._reset_defaults_button.setMinimumSize(150, 32)
        self._reset_defaults_button.setProperty("class", "WARNING")
        self._reset_defaults_button.clicked.connect(self._reset_to_defaults)

    def refresh_from_config(self) -> None:
        """Reload saved API keys and discard unsaved edits."""
        self._refresh_api_input(
            TreeNews.NEWS_SERVICE_NAME,
            self._tree_input,
            self._tree_password_button,
            self._tree_validation_label,
            "Enter your TreeOfAlpha API key here...",
        )
        self._refresh_api_input(
            PhoenixNews.NEWS_SERVICE_NAME,
            self._phoenix_input,
            self._phoenix_password_button,
            self._phoenix_validation_label,
            "Enter your Phoenix API key here...",
        )
        self._refresh_api_input(
            SynopticNews.NEWS_SERVICE_NAME,
            self._synoptic_input,
            self._synoptic_password_button,
            self._synoptic_validation_label,
            "Enter your Synoptic API key here...",
        )

    def _setup_api_widgets(
        self,
        *,
        line_edit: QtWidgets.QLineEdit,
        button: QtWidgets.QPushButton,
        password_button: QtWidgets.QPushButton,
        validation_label: QtWidgets.QLabel,
        service_name: str,
    ) -> None:
        """Configure one API-key input row."""
        line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        password_button.setCheckable(True)
        password_button.setObjectName("frameless")
        password_button.setIcon(QtGui.QPixmap(":/icons/eye_open"))
        password_button.toggled.connect(self._toggle_password_visibility)

        button.setProperty("class", "APPROVED")
        button.setMinimumSize(120, 30)
        button.clicked.connect(partial(self.record_news_source_key, service_name))

        validation_label.setWordWrap(True)
        validation_label.setObjectName("subText")
        validation_label.hide()

        line_edit.textChanged.connect(
            lambda _text, field=line_edit, action=button, label=validation_label: (
                self._validate_api_input(field, action, label)
            ),
        )

    def _load_saved_api_key(
        self,
        service_name: str,
        line_edit: QtWidgets.QLineEdit,
        placeholder: str,
    ) -> None:
        """Load one saved API key into its field."""
        try:
            current_key = keyring_manager.get_news_source_api_key(service_name, self._pass_guard)
            line_edit.setText(current_key)
        except KeyringPasswordNotFoundError:
            line_edit.clear()
            line_edit.setPlaceholderText(placeholder)

    def _refresh_api_input(
        self,
        service_name: str,
        line_edit: QtWidgets.QLineEdit,
        password_button: QtWidgets.QPushButton,
        validation_label: QtWidgets.QLabel,
        placeholder: str,
    ) -> None:
        """Reset one API input back to the saved state."""
        line_edit.blockSignals(True)
        self._load_saved_api_key(service_name, line_edit, placeholder)
        line_edit.blockSignals(False)
        line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        password_button.blockSignals(True)
        password_button.setChecked(False)
        password_button.setIcon(QtGui.QPixmap(":/icons/eye_open"))
        password_button.blockSignals(False)
        validation_label.hide()

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._news_source_bar)

        self._add_api_box(
            box=self._tree_box,
            box_layout=self._tree_box_layout,
            text_label=self._tree_text_label,
            line_edit=self._tree_input,
            password_button=self._tree_password_button,
            action_button=self._tree_button,
            validation_label=self._tree_validation_label,
        )
        self._add_api_box(
            box=self._phoenix_box,
            box_layout=self._phoenix_box_layout,
            text_label=self._phoenix_text_label,
            line_edit=self._phoenix_input,
            password_button=self._phoenix_password_button,
            action_button=self._phoenix_button,
            validation_label=self._phoenix_validation_label,
        )
        self._add_api_box(
            box=self._synoptic_box,
            box_layout=self._synoptic_box_layout,
            text_label=self._synoptic_text_label,
            line_edit=self._synoptic_input,
            password_button=self._synoptic_password_button,
            action_button=self._synoptic_button,
            validation_label=self._synoptic_validation_label,
        )

        reset_layout = QtWidgets.QHBoxLayout()
        reset_layout.addStretch()
        reset_layout.addWidget(self._reset_defaults_button)
        self._main_layout.addLayout(reset_layout)
        self._main_layout.addStretch()

    def _add_api_box(
        self,
        *,
        box: QtWidgets.QGroupBox,
        box_layout: QtWidgets.QVBoxLayout,
        text_label: QtWidgets.QLabel,
        line_edit: QtWidgets.QLineEdit,
        password_button: QtWidgets.QPushButton,
        action_button: QtWidgets.QPushButton,
        validation_label: QtWidgets.QLabel,
    ) -> None:
        """Add a configured API box to the main layout."""
        box_layout.addWidget(text_label)
        input_layout = QtWidgets.QHBoxLayout()
        input_layout.addWidget(line_edit)
        input_layout.addWidget(password_button)
        box_layout.addLayout(input_layout)
        box_layout.addWidget(validation_label)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(action_button)
        box_layout.addLayout(button_layout)
        box.setLayout(box_layout)
        self._main_layout.addWidget(box)

    def _validate_api_input(
        self,
        line_edit: QtWidgets.QLineEdit,
        button: QtWidgets.QPushButton,
        validation_label: QtWidgets.QLabel,
    ) -> bool:
        """Validate one API input field inline."""
        value = line_edit.text()
        stripped_value = value.strip()
        has_internal_whitespace = any(character.isspace() for character in stripped_value)
        if stripped_value and has_internal_whitespace:
            validation_label.setText("API keys cannot contain spaces or line breaks.")
            validation_label.show()
            button.setEnabled(False)
            return False

        validation_label.hide()
        button.setEnabled(True)
        return True

    @asyncSlot()
    async def record_news_source_key(self, news_source: str) -> None:
        """Record the news source API key in keyring."""
        text_source = {
            TreeNews.NEWS_SERVICE_NAME: (
                self._tree_input,
                self._tree_button,
                self._tree_validation_label,
            ),
            PhoenixNews.NEWS_SERVICE_NAME: (
                self._phoenix_input,
                self._phoenix_button,
                self._phoenix_validation_label,
            ),
            SynopticNews.NEWS_SERVICE_NAME: (
                self._synoptic_input,
                self._synoptic_button,
                self._synoptic_validation_label,
            ),
        }

        line_edit, button, validation_label = text_source[news_source]
        if not self._validate_api_input(line_edit, button, validation_label):
            Toast.show_message(
                "Fix the API key format before saving.",
                type_=ToastType.WARNING,
            )
            return

        new_key = line_edit.text().strip()
        try:
            old_key = keyring_manager.get_news_source_api_key(news_source, self._pass_guard)
        except KeyringPasswordNotFoundError:
            old_key = ""

        if new_key == old_key:
            Toast.show_message(
                "API key is equal to the old one.",
                type_=ToastType.WARNING,
            )
            return

        if not new_key:
            self._delete_news_source_key(news_source)
            await self._ui_controller.restart_news_manager()
            Toast.show_message("API key deleted.", type_=ToastType.WARNING)
            return

        keyring_manager.set_news_source_api_key(news_source, new_key, self._pass_guard)
        await self._ui_controller.restart_news_manager()
        Toast.show_message(
            "News source API key saved successfully!",
            type_=ToastType.SUCCESS,
        )

    def _delete_news_source_key(self, news_source: str) -> None:
        """Delete one stored news source key if it exists."""
        try:
            keyring.delete_password(f"{AppConfig.SERVICE_NAME}:news-source", news_source)
        except PasswordDeleteError:
            return

    @asyncSlot()
    async def _reset_to_defaults(self) -> None:
        """Clear all stored API keys and reset the section to defaults."""
        for service_name in (
            TreeNews.NEWS_SERVICE_NAME,
            PhoenixNews.NEWS_SERVICE_NAME,
            SynopticNews.NEWS_SERVICE_NAME,
        ):
            self._delete_news_source_key(service_name)

        for line_edit in (self._tree_input, self._phoenix_input, self._synoptic_input):
            line_edit.clear()

        await self._ui_controller.restart_news_manager()
        Toast.show_message("News API keys reset to defaults", type_=ToastType.SUCCESS)

    def _toggle_password_visibility(self, checked: bool) -> None:
        """Toggle the password visibility."""
        sender = self.sender()
        if not isinstance(sender, QtWidgets.QPushButton):
            return

        field_map = {
            self._tree_password_button: self._tree_input,
            self._phoenix_password_button: self._phoenix_input,
            self._synoptic_password_button: self._synoptic_input,
        }
        line_input = field_map.get(sender)
        if line_input is None:
            return

        line_input.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.Normal
            if checked
            else QtWidgets.QLineEdit.EchoMode.Password,
        )
        sender.setIcon(
            QtGui.QPixmap(":/icons/eye_closed") if checked else QtGui.QPixmap(":/icons/eye_open"),
        )


class NewsFiltersConfig(QtWidgets.QWidget):
    """Widget to control news filter configuration."""

    def __init__(
        self, ui_controller: UIController, parent: QtWidgets.QWidget | None = None
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._ui_controller = ui_controller

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._news_filters = TopBar("News Filters")
        self._news_scroll_area = QtWidgets.QScrollArea()
        self._news_scroll_widget = QtWidgets.QWidget()
        self._news_scroll_layout = QtWidgets.QVBoxLayout()

        self._keyword_matching_layout = QtWidgets.QVBoxLayout()
        self._keyword_matching_box = QtWidgets.QGroupBox("Keyword Matching - Filter")
        self._keyword_matching_add_btn = QtWidgets.QPushButton("Add Filter")

        self._data_matching_layout = QtWidgets.QVBoxLayout()
        self._data_matching_box = QtWidgets.QGroupBox("Data Matching - Filter")
        self._data_matching_add_btn = QtWidgets.QPushButton("Add Filter")

        self._reload_filters_btn = QtWidgets.QPushButton("Reload Saved Filters")
        self._reset_defaults_btn = QtWidgets.QPushButton("Reset to Defaults")
        self._save_filters_btn = QtWidgets.QPushButton("Save Filters")

        self._setup_widgets()
        self._setup_layout()
        self._populate_filters_from_db()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._news_scroll_area.setWidgetResizable(True)

        self._keyword_matching_add_btn.setMinimumSize(80, 30)
        self._keyword_matching_add_btn.setProperty("class", "APPROVED")
        self._keyword_matching_add_btn.clicked.connect(self._add_keyword_filter)

        self._data_matching_add_btn.setMinimumSize(80, 30)
        self._data_matching_add_btn.setProperty("class", "APPROVED")
        self._data_matching_add_btn.clicked.connect(self._add_data_filter)

        self._reload_filters_btn.setMinimumSize(150, 32)
        self._reload_filters_btn.clicked.connect(self._reload_saved_filters)

        self._reset_defaults_btn.setMinimumSize(150, 32)
        self._reset_defaults_btn.setProperty("class", "WARNING")
        self._reset_defaults_btn.clicked.connect(self._reset_to_defaults)

        self._save_filters_btn.setMinimumSize(150, 32)
        self._save_filters_btn.setProperty("class", "APPROVED")
        self._save_filters_btn.clicked.connect(self._save_filters)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(self._news_filters)
        self._news_scroll_widget.setLayout(self._news_scroll_layout)
        self._news_scroll_area.setWidget(self._news_scroll_widget)

        self._keyword_matching_layout.addWidget(
            self._keyword_matching_add_btn,
            alignment=QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        self._keyword_matching_box.setLayout(self._keyword_matching_layout)

        self._data_matching_layout.addWidget(
            self._data_matching_add_btn,
            alignment=QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        self._data_matching_box.setLayout(self._data_matching_layout)

        self._news_scroll_layout.addWidget(self._keyword_matching_box)
        self._news_scroll_layout.addWidget(self._data_matching_box)

        filter_buttons_layout = QtWidgets.QHBoxLayout()
        filter_buttons_layout.addStretch()
        filter_buttons_layout.addWidget(self._reload_filters_btn)
        filter_buttons_layout.addWidget(self._reset_defaults_btn)
        filter_buttons_layout.addWidget(self._save_filters_btn)
        self._news_scroll_layout.addLayout(filter_buttons_layout)
        self._news_scroll_layout.addStretch()
        self._main_layout.addWidget(self._news_scroll_area)

    def _populate_filters_from_db(self) -> None:
        """Rebuild the current filter widgets from the database."""
        self._clear_filter_layout(self._keyword_matching_layout, KeywordMatchingWidget)
        self._clear_filter_layout(self._data_matching_layout, DataMatchingWidget)

        for user_filter in AppConfig.get_all_user_filters():
            if int(user_filter.filter_type) == FilterType.KEYWORD_MATCHING:
                self._keyword_matching_layout.insertWidget(
                    self._keyword_matching_layout.count() - 1,
                    KeywordMatchingWidget(user_filter),
                )
            if int(user_filter.filter_type) == FilterType.DATA_MATCHING:
                self._data_matching_layout.insertWidget(
                    self._data_matching_layout.count() - 1,
                    DataMatchingWidget(user_filter),
                )

    def refresh_from_config(self) -> None:
        """Reload saved filters and discard unsaved edits."""
        self._populate_filters_from_db()

    def _clear_filter_layout(
        self,
        layout: QtWidgets.QVBoxLayout,
        widget_type: type[BaseFilterWidget],
    ) -> None:
        """Delete all filter widgets of one layout type."""
        widgets = [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if isinstance(layout.itemAt(index).widget(), widget_type)
        ]
        for widget in widgets:
            layout.removeWidget(widget)
            widget.deleteLater()

    def _iter_filter_widgets(self) -> list[BaseFilterWidget]:
        """Return all visible filter widgets."""
        widgets: list[BaseFilterWidget] = []
        for layout in (self._keyword_matching_layout, self._data_matching_layout):
            for index in range(layout.count()):
                widget = layout.itemAt(index).widget()
                if isinstance(widget, BaseFilterWidget):
                    widgets.append(widget)
        return widgets

    def _add_keyword_filter(self) -> None:
        """Add a new keyword filter."""
        user_filter = UserFilter(
            filter_type=FilterType.KEYWORD_MATCHING,
            match_pattern=orjson.dumps({"keyword": ""}).decode("utf-8"),
            action_type=ActionType.COIN_ASSOCIATION,
            action_args=orjson.dumps({"coin": "BTC", "color": [255, 0, 0]}).decode("utf-8"),
        )
        self._keyword_matching_layout.insertWidget(
            self._keyword_matching_layout.count() - 1,
            KeywordMatchingWidget(user_filter),
        )

    def _add_data_filter(self) -> None:
        """Add a new data filter."""
        user_filter = UserFilter(
            filter_type=FilterType.DATA_MATCHING,
            match_pattern=orjson.dumps({"keyword": "", "data_key": "coin"}).decode("utf-8"),
            action_type=ActionType.COIN_ASSOCIATION,
            action_args=orjson.dumps({"coin": "BTC"}).decode("utf-8"),
        )
        self._data_matching_layout.insertWidget(
            self._data_matching_layout.count() - 1,
            DataMatchingWidget(user_filter),
        )

    def _reload_saved_filters(self) -> None:
        """Reload filters from the database."""
        self._populate_filters_from_db()
        Toast.show_message("Reloaded saved filters", type_=ToastType.SUCCESS)

    def _reset_to_defaults(self) -> None:
        """Reset filters to the default empty state."""
        AppConfig.delete_all_user_filters()
        self._populate_filters_from_db()
        self._ui_controller.update_news_filters()
        Toast.show_message("News filters reset to defaults", type_=ToastType.SUCCESS)

    def _save_filters(self) -> None:
        """Save filters to the database."""
        validation_errors = [
            error
            for widget in self._iter_filter_widgets()
            if (error := widget.validation_error()) is not None
        ]
        if validation_errors:
            for error in validation_errors:
                LOGGER.warning("News filter validation warning: %s", error)
            Toast.show_message(
                "Resolve filter warnings before saving.",
                type_=ToastType.WARNING,
            )
            return

        for widget in self._iter_filter_widgets():
            widget.write_to_db()

        self._ui_controller.update_news_filters()
        Toast.show_message("News Filters updated", type_=ToastType.SUCCESS)


class ColorButton(QtWidgets.QPushButton):
    """Custom Qt widget to show a chosen color."""

    color_changed = QtCore.Signal(object)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        color: QtGui.QColor,
    ) -> None:
        """Initialize ColorButton."""
        super().__init__(parent)
        self.setObjectName("buttonColor")

        self._color: QtGui.QColor = color or QtGui.QColor(255, 0, 0)
        self.pressed.connect(self.on_color_picker)
        self.set_color(color)

    @property
    def color(self) -> QtGui.QColor:
        """Return current color."""
        return self._color

    def set_color(self, color: QtGui.QColor) -> None:
        """Set color."""
        if color != self._color:
            self._color = color
            self.color_changed.emit(color)

        if self._color:
            self.setStyleSheet(
                f"QPushButton#buttonColor {{background-color: {self._color.name()};}}",
            )
        else:
            self.setStyleSheet("")

    def on_color_picker(self) -> None:
        """Show color-picker dialog to select color."""
        color_dialog = QtWidgets.QColorDialog(self)
        color_dialog.setOption(
            QtWidgets.QColorDialog.ColorDialogOption.ShowAlphaChannel,
            False,
        )
        color_dialog.setOption(
            QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog,
            True,
        )

        if color_dialog.exec_():
            self.set_color(color_dialog.currentColor())


class BaseFilterWidget(QtWidgets.QFrame):
    """Base widget to control one filter."""

    def __init__(
        self,
        user_filter: UserFilter,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self._user_filter = user_filter
        self._to_delete = True

    def on_delete(self) -> None:
        """Handle delete."""
        self.hide()
        self._to_delete = True

    def validation_error(self) -> str | None:
        """Return an optional validation error for the current filter state."""
        return None

    def write_to_db(self) -> None:
        """Write user_filter to database."""
        if self._to_delete:
            filter_id = self._user_filter.get_id()
            if filter_id is not None:
                AppConfig.delete_user_filter(int(filter_id))
            self.deleteLater()
            return


class KeywordMatchingWidget(BaseFilterWidget):
    """Widget to control keyword matching filter."""

    def __init__(
        self,
        user_filter: UserFilter,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(user_filter=user_filter, parent=parent)

        self._sfx = QSoundEffect()

        self._main_layout = QtWidgets.QHBoxLayout(self)
        self._if_label = QtWidgets.QLabel("IF")
        self._match_pattern = QtWidgets.QLineEdit()
        self._then_label = QtWidgets.QLabel("THEN")
        self._action_combo = QtWidgets.QComboBox()
        self._sound_combo = QtWidgets.QComboBox()
        self._sound_button = QtWidgets.QPushButton()
        self._coin_line = QtWidgets.QLineEdit()
        self._color_picker = ColorButton(color=QtGui.QColor("red"))
        self._delete_btn = QtWidgets.QPushButton()

        self._setup_widgets()
        self._setup_layout()

        self.reset_to_current()
        self.setMinimumHeight(self.sizeHint().height())

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setObjectName("config_item")
        self._if_label.setObjectName("title")

        self._match_pattern.setPlaceholderText("Pattern to Match...")
        self._match_pattern.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        for action in FILTER_ACTIONS_MAP:
            self._action_combo.addItem(action.name.capitalize(), userData=action)
        self._action_combo.currentIndexChanged.connect(self.on_action_change)

        self._then_label.setObjectName("title")
        self._coin_line.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        for path in list_resources_from_prefix("sfx"):
            self._sound_combo.addItem(path, userData=f":/sfx/{path}")
        self._sound_button.setIcon(QtGui.QPixmap(":/icons/music"))
        self._sound_button.setProperty("class", "borderless")
        self._sound_button.setToolTip("Play Sound")
        self._sound_button.clicked.connect(self.on_play_sound)

        self._coin_line.setPlaceholderText("Coin to assign")

        self._delete_btn.setIcon(QtGui.QPixmap(":/icons/delete_icon"))
        self._delete_btn.setMinimumSize(32, 32)
        self._delete_btn.setProperty("class", "borderless")
        self._delete_btn.setToolTip("Delete Filter")
        self._delete_btn.clicked.connect(self.on_delete)

    def on_play_sound(self) -> None:
        """Play sound."""
        sfx_path = self._sound_combo.itemData(self._sound_combo.currentIndex())
        self._sfx.setSource(QtCore.QUrl.fromLocalFile(sfx_path))
        self._sfx.play()

    def on_action_change(self, index: int) -> None:
        """Handle action change."""
        action = self._action_combo.itemData(index)
        if action == ActionType.COIN_ASSOCIATION:
            self._sound_combo.setVisible(False)
            self._sound_button.setVisible(False)
            self._coin_line.setVisible(True)
            self._color_picker.setVisible(True)
        elif action == ActionType.SOUND_ASSOCIATION:
            self._sound_combo.setVisible(True)
            self._sound_button.setVisible(True)
            self._coin_line.setVisible(False)
            self._color_picker.setVisible(True)
        elif action == ActionType.IGNORE:
            self._sound_combo.setVisible(False)
            self._sound_button.setVisible(False)
            self._coin_line.setVisible(False)
            self._color_picker.setVisible(False)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(
            self._if_label,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        self._main_layout.addWidget(self._match_pattern)
        self._main_layout.addWidget(
            self._then_label,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        self._main_layout.addWidget(self._action_combo)
        self._main_layout.addWidget(self._sound_combo)
        self._main_layout.addWidget(self._sound_button)
        self._main_layout.addWidget(self._coin_line)
        self._main_layout.addWidget(self._color_picker)
        self._main_layout.addWidget(self._delete_btn)

    def reset_to_current(self) -> None:
        """Reset values to current filter."""
        match_pattern = orjson.loads(str(self._user_filter.match_pattern))
        if keyword := match_pattern.get("keyword", ""):
            self._match_pattern.setText(keyword)

        action_type = ActionType(cast("int", self._user_filter.action_type))
        action_index = self._action_combo.findData(action_type)
        self._action_combo.setCurrentIndex(action_index)

        action_args = orjson.loads(str(self._user_filter.action_args))
        if sound_path := action_args.get("sound_path", ""):
            sound_index = self._sound_combo.findData(sound_path)
            self._sound_combo.setCurrentIndex(sound_index)
        if coin := action_args.get("coin", ""):
            self._coin_line.setText(coin)
        if color := action_args.get("color", ""):
            self._color_picker.set_color(QtGui.QColor(*color))

        self.on_action_change(action_index)
        self._to_delete = False

    def validation_error(self) -> str | None:
        """Return a validation error for invalid keyword filters."""
        if self._to_delete:
            return None
        if not self._match_pattern.text().strip():
            return "Keyword filter requires a match pattern."
        if self._coin_line.isVisible() and not self._coin_line.text().strip():
            return "Keyword filter coin-association requires a target coin."
        return None

    def write_to_db(self) -> None:
        """Write user_filter to database."""
        super().write_to_db()

        self._user_filter.match_pattern = orjson.dumps(  # type: ignore[assignment]
            {"keyword": self._match_pattern.text()},
        ).decode("utf-8")
        self._user_filter.action_type = self._action_combo.currentData()  # type: ignore[assignment]
        action_args: dict[str, object] = {}
        if self._sound_combo.isVisible():
            action_args["sound_path"] = self._sound_combo.currentData()
        if self._coin_line.isVisible():
            action_args["coin"] = self._coin_line.text()
        if self._color_picker.isVisible():
            action_args["color"] = (
                self._color_picker.color.red(),
                self._color_picker.color.green(),
                self._color_picker.color.blue(),
            )

        self._user_filter.action_args = orjson.dumps(action_args).decode("utf-8")  # type: ignore[assignment]
        AppConfig.write_model_to_db(self._user_filter)


class DataMatchingWidget(BaseFilterWidget):
    """Widget to control data matching filter."""

    def __init__(
        self,
        user_filter: UserFilter,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(user_filter=user_filter, parent=parent)
        self._sfx = QSoundEffect()

        self._main_layout = QtWidgets.QHBoxLayout(self)
        self._if_label = QtWidgets.QLabel("IF")
        self._match_pattern = QtWidgets.QLineEdit()
        self._in_label = QtWidgets.QLabel("IN")
        self._data_field = QtWidgets.QComboBox()
        self._then_label = QtWidgets.QLabel("THEN")
        self._action_combo = QtWidgets.QComboBox()
        self._sound_combo = QtWidgets.QComboBox()
        self._sound_button = QtWidgets.QPushButton()
        self._coin_line = QtWidgets.QLineEdit()
        self._delete_btn = QtWidgets.QPushButton()

        self._setup_widgets()
        self._setup_layout()

        self.reset_to_current()
        self.setMinimumHeight(self.sizeHint().height())

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setObjectName("config_item")
        self._if_label.setObjectName("title")

        self._match_pattern.setPlaceholderText("Pattern to Match...")
        self._match_pattern.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        self._in_label.setObjectName("title")
        for field in ["title", "quoter", "coin", "source", "feed"]:
            self._data_field.addItem(field.capitalize(), userData=field)

        for action in FILTER_ACTIONS_MAP:
            self._action_combo.addItem(action.name.capitalize(), userData=action)
        self._action_combo.currentIndexChanged.connect(self.on_action_change)

        self._then_label.setObjectName("title")
        self._coin_line.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        for path in list_resources_from_prefix("sfx"):
            self._sound_combo.addItem(path, userData=f":/sfx/{path}")
        self._sound_button.setIcon(QtGui.QPixmap(":/icons/music"))
        self._sound_button.setProperty("class", "borderless")
        self._sound_button.setToolTip("Play Sound")
        self._sound_button.clicked.connect(self.on_play_sound)

        self._coin_line.setPlaceholderText("Coin to assign")

        self._delete_btn.setIcon(QtGui.QPixmap(":/icons/delete_icon"))
        self._delete_btn.setMinimumSize(32, 32)
        self._delete_btn.setProperty("class", "borderless")
        self._delete_btn.setToolTip("Delete Filter")
        self._delete_btn.clicked.connect(self.on_delete)

    def on_play_sound(self) -> None:
        """Play sound."""
        sfx_path = self._sound_combo.itemData(self._sound_combo.currentIndex())
        self._sfx.setSource(QtCore.QUrl.fromLocalFile(sfx_path))
        self._sfx.play()

    def on_action_change(self, index: int) -> None:
        """Handle action change."""
        action = self._action_combo.itemData(index)
        if action == ActionType.COIN_ASSOCIATION:
            self._sound_combo.setVisible(False)
            self._sound_button.setVisible(False)
            self._coin_line.setVisible(True)
        elif action == ActionType.SOUND_ASSOCIATION:
            self._sound_combo.setVisible(True)
            self._sound_button.setVisible(True)
            self._coin_line.setVisible(False)
        elif action == ActionType.IGNORE:
            self._sound_combo.setVisible(False)
            self._sound_button.setVisible(False)
            self._coin_line.setVisible(False)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self._main_layout.addWidget(
            self._if_label,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        self._main_layout.addWidget(self._match_pattern)
        self._main_layout.addWidget(
            self._in_label,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        self._main_layout.addWidget(self._data_field)
        self._main_layout.addWidget(
            self._then_label,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        self._main_layout.addWidget(self._action_combo)
        self._main_layout.addWidget(self._sound_combo)
        self._main_layout.addWidget(self._sound_button)
        self._main_layout.addWidget(self._coin_line)
        self._main_layout.addWidget(self._delete_btn)

    def reset_to_current(self) -> None:
        """Reset values to current filter."""
        match_pattern = orjson.loads(str(self._user_filter.match_pattern))
        if keyword := match_pattern.get("keyword", ""):
            self._match_pattern.setText(keyword)
        if data_key := match_pattern.get("data_key", ""):
            data_index = self._data_field.findData(data_key)
            self._data_field.setCurrentIndex(data_index)

        action_type = ActionType(cast("int", self._user_filter.action_type))
        action_index = self._action_combo.findData(action_type)
        self._action_combo.setCurrentIndex(action_index)

        action_args = orjson.loads(str(self._user_filter.action_args))
        if sound_path := action_args.get("sound_path", ""):
            sound_index = self._sound_combo.findData(sound_path)
            self._sound_combo.setCurrentIndex(sound_index)
        if coin := action_args.get("coin", ""):
            self._coin_line.setText(coin)

        self.on_action_change(action_index)
        self._to_delete = False

    def validation_error(self) -> str | None:
        """Return a validation error for invalid data filters."""
        if self._to_delete:
            return None
        if not self._match_pattern.text().strip():
            return "Data filter requires a match pattern."
        if self._coin_line.isVisible() and not self._coin_line.text().strip():
            return "Data filter coin-association requires a target coin."
        return None

    def write_to_db(self) -> None:
        """Write user_filter to database."""
        super().write_to_db()

        self._user_filter.match_pattern = orjson.dumps(  # type: ignore[assignment]
            {
                "keyword": self._match_pattern.text(),
                "data_key": self._data_field.currentData(),
            },
        ).decode("utf-8")
        self._user_filter.action_type = self._action_combo.currentData()  # type: ignore[assignment]
        action_args: dict[str, object] = {}
        if self._sound_combo.isVisible():
            action_args["sound_path"] = self._sound_combo.currentData()
        if self._coin_line.isVisible():
            action_args["coin"] = self._coin_line.text()

        self._user_filter.action_args = orjson.dumps(action_args).decode("utf-8")  # type: ignore[assignment]
        AppConfig.write_model_to_db(self._user_filter)


NewsConfig = NewsSourceConfig
