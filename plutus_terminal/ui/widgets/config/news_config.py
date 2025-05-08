"""Widget to control news configuration."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Optional

import orjson
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtMultimedia import QSoundEffect
from qasync import asyncSlot

from plutus_terminal.core import keyring_manager
from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.db.models import UserFilter
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


class NewsConfig(QtWidgets.QWidget):
    """Widget to control news configuration."""

    def __init__(
        self, ui_controller: UIController, parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self._ui_controller = ui_controller
        self._pass_guard = self._ui_controller.pass_guard

        self._main_layout = QtWidgets.QVBoxLayout()

        self._news_source_bar = TopBar("News Source API Keys")
        self._tree_box = QtWidgets.QGroupBox("TreeOfAlpha API Key")
        self._tree_box_layout = QtWidgets.QVBoxLayout()
        self._tree_text_label = QtWidgets.QLabel()
        self._tree_input = QtWidgets.QLineEdit()
        self._tree_button = QtWidgets.QPushButton("Update API Key")
        self._tree_password_button = QtWidgets.QPushButton()

        self._phoenix_box = QtWidgets.QGroupBox("Phoenix API Key")
        self._phoenix_box_layout = QtWidgets.QVBoxLayout()
        self._phoenix_text_label = QtWidgets.QLabel()
        self._phoenix_input = QtWidgets.QLineEdit()
        self._phoenix_button = QtWidgets.QPushButton("Update API Key")
        self._phoenix_password_button = QtWidgets.QPushButton()

        self._synoptic_box = QtWidgets.QGroupBox("Synoptic API Key")
        self._synoptic_box_layout = QtWidgets.QVBoxLayout()
        self._synoptic_text_label = QtWidgets.QLabel()
        self._synoptic_input = QtWidgets.QLineEdit()
        self._synoptic_button = QtWidgets.QPushButton("Update API Key")
        self._synoptic_password_button = QtWidgets.QPushButton()

        self._news_filters = TopBar("News Filters")
        self._news_scroll_area = QtWidgets.QScrollArea()
        self._news_scroll_wdiget = QtWidgets.QWidget()
        self._news_scroll_layout = QtWidgets.QVBoxLayout()

        self._keyword_matching_layout = QtWidgets.QVBoxLayout()
        self._keyword_matching_box = QtWidgets.QGroupBox("Keyword Matching - Filter")
        self._keyword_matching_add_btn = QtWidgets.QPushButton("Add filter")

        self._data_matching_layout = QtWidgets.QVBoxLayout()
        self._data_matching_box = QtWidgets.QGroupBox("Data Matching - Filter")
        self._data_matching_add_btn = QtWidgets.QPushButton("Add filter")

        self._reset_filters_btn = QtWidgets.QPushButton("Reset Filters")
        self._save_filters_btn = QtWidgets.QPushButton("Save Filters")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:  # noqa: PLR0915
        """Config widgets."""
        self._tree_text_label.setWordWrap(True)
        self._tree_text_label.setText(
            """Add your TreeOfAlpha API key below if you are a paid subscriber.<br>"""
            """To get your API key, go to """
            """<a href="https://news.treeofalpha.com/api/api_key"""
            """style="color:rgb(80, 210, 180)">"""
            """https://news.treeofalpha.com/api/api_key</a>""",
        )
        self._tree_text_label.setOpenExternalLinks(True)
        self._tree_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._tree_password_button.setCheckable(True)
        self._tree_password_button.setObjectName("frameless")
        self._tree_password_button.setIcon(QtGui.QPixmap(":/icons/eye_open"))
        self._tree_password_button.toggled.connect(self._toggle_password_visibility)
        self._tree_button.setProperty("class", "LONG")
        self._tree_button.setMinimumSize(120, 30)
        try:
            current_tree_key = keyring_manager.get_news_source_api_key(
                TreeNews.NEWS_SERVICE_NAME,
                self._pass_guard,
            )
            self._tree_input.setText(current_tree_key)
        except keyring_manager.KeyringPasswordNotFoundError:
            self._tree_input.setPlaceholderText(
                "Enter your TreeOfAlpha API key here...",
            )

        self._phoenix_text_label.setWordWrap(True)
        self._phoenix_text_label.setText(
            """Add your PhoenixNews API key below if you are a paid subscriber.<br>"""
            """To get your API key, go to """
            """<a href="https://phoenixnews.io", style="color:rgb(80, 210, 180)">"""
            """https://phoenixnews.io</a>""",
        )
        self._phoenix_text_label.setOpenExternalLinks(True)
        self._phoenix_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._phoenix_password_button.setCheckable(True)
        self._phoenix_password_button.setObjectName("frameless")
        self._phoenix_password_button.setIcon(QtGui.QPixmap(":/icons/eye_open"))
        self._phoenix_password_button.toggled.connect(self._toggle_password_visibility)
        self._phoenix_button.setProperty("class", "LONG")
        self._phoenix_button.setMinimumSize(120, 30)
        try:
            current_phoenix_key = keyring_manager.get_news_source_api_key(
                PhoenixNews.NEWS_SERVICE_NAME,
                self._pass_guard,
            )
            self._phoenix_input.setText(current_phoenix_key)
        except keyring_manager.KeyringPasswordNotFoundError:
            self._phoenix_input.setPlaceholderText("Enter your Phoenix API key here...")

        self._synoptic_text_label.setWordWrap(True)
        self._synoptic_text_label.setText(
            """Add your Synoptic API key below.<br>"""
            """To get your API key, go to """
            """<a href="https://synoptic.com/p/settings/api-keys", style="color:rgb(80, 210, 180)">"""
            """https://synoptic.com/p/settings/api-keys</a>""",
        )
        self._synoptic_text_label.setOpenExternalLinks(True)
        self._synoptic_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._synoptic_password_button.setCheckable(True)
        self._synoptic_password_button.setObjectName("frameless")
        self._synoptic_password_button.setIcon(QtGui.QPixmap(":/icons/eye_open"))
        self._synoptic_password_button.toggled.connect(self._toggle_password_visibility)
        self._synoptic_button.setProperty("class", "LONG")
        self._synoptic_button.setMinimumSize(120, 30)
        try:
            current_synoptic_key = keyring_manager.get_news_source_api_key(
                SynopticNews.NEWS_SERVICE_NAME,
                self._pass_guard,
            )
            self._synoptic_input.setText(current_synoptic_key)
        except keyring_manager.KeyringPasswordNotFoundError:
            self._synoptic_input.setPlaceholderText("Enter your Synoptic API key here...")

        self._tree_button.clicked.connect(
            partial(self.record_news_source_key, TreeNews.NEWS_SERVICE_NAME),
        )
        self._phoenix_button.clicked.connect(
            partial(self.record_news_source_key, PhoenixNews.NEWS_SERVICE_NAME),
        )
        self._synoptic_button.clicked.connect(
            partial(self.record_news_source_key, SynopticNews.NEWS_SERVICE_NAME),
        )

        self._news_scroll_area.setWidgetResizable(True)

        self._keyword_matching_add_btn.setMinimumSize(80, 30)
        self._keyword_matching_add_btn.setProperty("class", "LONG")
        self._keyword_matching_add_btn.clicked.connect(self._add_keyword_filter)

        self._data_matching_add_btn.setMinimumSize(80, 30)
        self._data_matching_add_btn.setProperty("class", "LONG")
        self._data_matching_add_btn.clicked.connect(self._add_data_filter)

        self._reset_filters_btn.setMinimumSize(80, 30)
        self._reset_filters_btn.clicked.connect(self._reset_filters)

        self._save_filters_btn.setMinimumSize(80, 30)
        self._save_filters_btn.setProperty("class", "LONG")
        self._save_filters_btn.clicked.connect(self._save_filters)

        user_filters = AppConfig.get_all_user_filters()
        for user_filter in user_filters:
            if int(user_filter.filter_type) == FilterType.KEYWORD_MATCHING:
                self._keyword_matching_layout.addWidget(KeywordMatchingWidget(user_filter))
            if int(user_filter.filter_type) == FilterType.DATA_MATCHING:
                self._data_matching_layout.addWidget(DataMatchingWidget(user_filter))

    def _setup_layout(self) -> None:  # noqa: PLR0915
        """Config layout."""
        self._main_layout.addWidget(self._news_source_bar)
        self._tree_box_layout.addWidget(self._tree_text_label)
        tree_input_layout = QtWidgets.QHBoxLayout()
        tree_input_layout.addWidget(self._tree_input)
        tree_input_layout.addWidget(self._tree_password_button)

        self._tree_box_layout.addLayout(tree_input_layout)
        tree_button_layout = QtWidgets.QHBoxLayout()
        tree_button_layout.addStretch()
        tree_button_layout.addWidget(self._tree_button)
        self._tree_box_layout.addLayout(tree_button_layout)
        self._tree_box.setLayout(self._tree_box_layout)
        self._main_layout.addWidget(self._tree_box)

        self._phoenix_box_layout.addWidget(self._phoenix_text_label)
        phoenix_input_layout = QtWidgets.QHBoxLayout()
        phoenix_input_layout.addWidget(self._phoenix_input)
        phoenix_input_layout.addWidget(self._phoenix_password_button)

        self._phoenix_box_layout.addLayout(phoenix_input_layout)
        phoenix_button_layout = QtWidgets.QHBoxLayout()
        phoenix_button_layout.addStretch()
        phoenix_button_layout.addWidget(self._phoenix_button)
        self._phoenix_box_layout.addLayout(phoenix_button_layout)
        self._phoenix_box.setLayout(self._phoenix_box_layout)
        self._main_layout.addWidget(self._phoenix_box)

        self._synoptic_box_layout.addWidget(self._synoptic_text_label)
        synoptic_input_layout = QtWidgets.QHBoxLayout()
        synoptic_input_layout.addWidget(self._synoptic_input)
        synoptic_input_layout.addWidget(self._synoptic_password_button)
        self._synoptic_box_layout.addLayout(synoptic_input_layout)
        synoptic_button_layout = QtWidgets.QHBoxLayout()
        synoptic_button_layout.addStretch()
        synoptic_button_layout.addWidget(self._synoptic_button)
        self._synoptic_box_layout.addLayout(synoptic_button_layout)
        self._synoptic_box.setLayout(self._synoptic_box_layout)
        self._main_layout.addWidget(self._synoptic_box)

        self._main_layout.addWidget(self._news_filters)

        self._news_scroll_wdiget.setLayout(self._news_scroll_layout)
        self._news_scroll_area.setWidget(self._news_scroll_wdiget)

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
        filter_buttons_layout.addWidget(self._reset_filters_btn)
        filter_buttons_layout.addWidget(self._save_filters_btn)
        self._news_scroll_layout.addLayout(filter_buttons_layout)
        self._news_scroll_layout.addStretch()
        self._main_layout.addWidget(self._news_scroll_area)

        self.setLayout(self._main_layout)

    @asyncSlot()
    async def record_news_source_key(self, news_source: str) -> None:
        """Record the news source API key in keyring.

        Args:
            news_source: name of the news source,
        """
        text_source = {
            TreeNews.NEWS_SERVICE_NAME: self._tree_input.text(),
            PhoenixNews.NEWS_SERVICE_NAME: self._phoenix_input.text(),
            SynopticNews.NEWS_SERVICE_NAME: self._synoptic_input.text(),
        }

        new_key = text_source[news_source].strip()
        old_key = keyring_manager.get_news_source_api_key(
            news_source,
            self._pass_guard,
        )
        if new_key == old_key:
            Toast.show_message(
                "API key is equal to the old one.",
                type_=ToastType.WARNING,
            )
            return

        if not new_key:
            Toast.show_message(
                "API key cannot be empty.",
                type_=ToastType.ERROR,
            )
            return

        keyring_manager.set_news_source_api_key(
            news_source,
            new_key,
            self._pass_guard,
        )

        await self._ui_controller.restart_news_manager()
        Toast.show_message(
            "News source API key saved successfully!",
            type_=ToastType.SUCCESS,
        )

    def _toggle_password_visibility(self, checked: bool) -> None:
        """Toggle the password visibility.

        Args:
            checked: True if the button is checked.
        """
        sender = self.sender()
        line_input = None
        password_button = None
        if sender == self._tree_password_button:
            line_input = self._tree_input
            password_button = self._tree_password_button
        if sender == self._phoenix_password_button:
            line_input = self._phoenix_input
            password_button = self._phoenix_password_button
        if sender == self._synoptic_password_button:
            line_input = self._synoptic_input
            password_button = self._synoptic_password_button

        if line_input is None or password_button is None:
            return

        line_input.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.Normal
            if checked
            else QtWidgets.QLineEdit.EchoMode.Password
        )
        password_button.setIcon(
            QtGui.QPixmap(":/icons/eye_closed") if checked else QtGui.QPixmap(":/icons/eye_open")
        )

    def _add_keyword_filter(self) -> None:
        """Add a new keyword filter."""
        user_filter = UserFilter(
            filter_type=FilterType.KEYWORD_MATCHING,
            match_pattern=orjson.dumps({"keyword": ""}).decode("utf-8"),
            action_type=ActionType.COIN_ASSOCIATION,
            action_args=orjson.dumps({"coin": "BTC", "color": [255, 0, 0]}).decode(
                "utf-8",
            ),
        )
        self._keyword_matching_layout.insertWidget(
            self._keyword_matching_layout.count() - 1,
            KeywordMatchingWidget(user_filter),
        )

    def _add_data_filter(self) -> None:
        """Add a new data filter."""
        user_filter = UserFilter(
            filter_type=FilterType.DATA_MATCHING,
            match_pattern=orjson.dumps({"keyword": "", "data_key": "coin"}).decode(
                "utf-8",
            ),
            action_type=ActionType.COIN_ASSOCIATION,
            action_args=orjson.dumps({"coin": "BTC"}).decode("utf-8"),
        )
        self._data_matching_layout.insertWidget(
            self._data_matching_layout.count() - 1,
            DataMatchingWidget(user_filter),
        )

    def _reset_filters(self) -> None:
        """Reset filters to match database."""
        # Delete all current filters widgets
        keyword_matching_widgets = [
            self._keyword_matching_layout.itemAt(index).widget()
            for index in range(self._keyword_matching_layout.count())
            if isinstance(
                self._keyword_matching_layout.itemAt(index).widget(),
                KeywordMatchingWidget,
            )
        ]
        for widget in keyword_matching_widgets:
            self._keyword_matching_layout.removeWidget(widget)
            widget.deleteLater()

        data_matching_widgets = [
            self._data_matching_layout.itemAt(index).widget()
            for index in range(self._data_matching_layout.count())
            if isinstance(
                self._data_matching_layout.itemAt(index).widget(),
                DataMatchingWidget,
            )
        ]
        for widget in data_matching_widgets:
            self._data_matching_layout.removeWidget(widget)
            widget.deleteLater()

        # Create new filters widget matching database
        user_filters = AppConfig.get_all_user_filters()
        for user_filter in user_filters:
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

    def _save_filters(self) -> None:
        """Save filters to database."""
        for index in range(self._keyword_matching_layout.count()):
            widget = self._keyword_matching_layout.itemAt(index).widget()
            if isinstance(widget, KeywordMatchingWidget):
                widget.write_to_db()

        for index in range(self._data_matching_layout.count()):
            widget = self._data_matching_layout.itemAt(index).widget()
            if isinstance(widget, DataMatchingWidget):
                widget.write_to_db()

        self._ui_controller.update_news_filters()
        Toast.show_message("News Filters updated", type_=ToastType.SUCCESS)


class ColorButton(QtWidgets.QPushButton):
    """Custom Qt Widget to show a chosen color."""

    color_changed = QtCore.Signal(object)

    def __init__(self, *args: object, color: QtGui.QColor, **kwargs: dict) -> None:
        """Initialize ColorButton."""
        super().__init__(*args, **kwargs)  # type: ignore
        self.setObjectName("buttonColor")

        self._color: QtGui.QColor = color if color else QtGui.QColor(255, 0, 0)
        self.pressed.connect(self.on_color_picker)

        # Set the initial/default state.
        self.set_color(color)

    @property
    def color(self) -> QtGui.QColor:
        """Returns current color.

        Returns:
            QtGui.QColor: Color of the button.
        """
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
    """Base Widget to control filter."""

    def __init__(
        self,
        user_filter: UserFilter,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self._user_filter = user_filter
        self._to_delete = True

    def on_delete(self) -> None:
        """Handle delete."""
        self.hide()
        self._to_delete = True

    def write_to_db(self) -> None:
        """Write user_filter to database."""
        if self._to_delete:
            AppConfig.delete_user_filter(self._user_filter.id)  # type: ignore
            self.deleteLater()
            return


class KeywordMatchingWidget(BaseFilterWidget):
    """Widget to control keyword matching filter."""

    def __init__(
        self,
        user_filter: UserFilter,
        parent: Optional[QtWidgets.QWidget] = None,
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
        """Configure Widgets."""
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
            self._sound_combo.addItem(
                path,
                userData=f":/sfx/{path}",
            )
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

        self.setLayout(self._main_layout)

    def reset_to_current(self) -> None:
        """Reset values to current filter."""
        match_pattern = orjson.loads(str(self._user_filter.match_pattern))
        if keyword := match_pattern.get("keyword", ""):
            self._match_pattern.setText(keyword)
        action_index = self._action_combo.findData(
            ActionType(int(self._user_filter.action_type)),  # type: ignore
        )
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

    def write_to_db(self) -> None:
        """Write user_filter to database."""
        super().write_to_db()

        self._user_filter.match_pattern = orjson.dumps(  # type: ignore
            {"keyword": self._match_pattern.text()},
        ).decode("utf-8")
        self._user_filter.action_type = self._action_combo.currentData()  # type: ignore
        action_args = {}
        if self._sound_combo.isVisible():
            action_args["sound_path"] = self._sound_combo.currentData()  # type: ignore
        if self._coin_line.isVisible():
            action_args["coin"] = self._coin_line.text()
        if self._color_picker.isVisible():
            action_args["color"] = self._color_picker.color.toTuple()[0:3]  # type: ignore

        self._user_filter.action_args = orjson.dumps(action_args).decode("utf-8")  # type: ignore
        AppConfig.write_model_to_db(self._user_filter)


class DataMatchingWidget(BaseFilterWidget):
    """Widget to control data matching filter."""

    def __init__(
        self,
        user_filter: UserFilter,
        parent: Optional[QtWidgets.QWidget] = None,
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
        """Configure Widgets."""
        self.setObjectName("config_item")

        self._if_label.setObjectName("title")

        self._match_pattern.setPlaceholderText("Pattern to Match...")
        self._match_pattern.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        self._in_label.setObjectName("title")
        valid_fields = ["title", "quoter", "coin", "source", "feed"]
        for field in valid_fields:
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
            self._sound_combo.addItem(
                path,
                userData=f":/sfx/{path}",
            )
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

        self.setLayout(self._main_layout)

    def reset_to_current(self) -> None:
        """Reset values to current filter."""
        match_pattern = orjson.loads(str(self._user_filter.match_pattern))
        if keyword := match_pattern.get("keyword", ""):
            self._match_pattern.setText(keyword)
        if data_key := match_pattern.get("data_key", ""):
            data_index = self._data_field.findData(data_key)
            self._data_field.setCurrentIndex(data_index)

        action_index = self._action_combo.findData(
            ActionType(int(self._user_filter.action_type)),  # type: ignore
        )
        self._action_combo.setCurrentIndex(action_index)

        action_args = orjson.loads(str(self._user_filter.action_args))

        if sound_path := action_args.get("sound_path", ""):
            sound_index = self._sound_combo.findData(sound_path)
            self._sound_combo.setCurrentIndex(sound_index)

        if coin := action_args.get("coin", ""):
            self._coin_line.setText(coin)

        self.on_action_change(action_index)
        self._to_delete = False

    def write_to_db(self) -> None:
        """Write user_filter to database."""
        super().write_to_db()

        self._user_filter.match_pattern = orjson.dumps(  # type: ignore
            {
                "keyword": self._match_pattern.text(),
                "data_key": self._data_field.currentData(),
            },
        ).decode("utf-8")
        self._user_filter.action_type = self._action_combo.currentData()  # type: ignore
        action_args = {}
        if self._sound_combo.isVisible():
            action_args["sound_path"] = self._sound_combo.currentData()  # type: ignore
        if self._coin_line.isVisible():
            action_args["coin"] = self._coin_line.text()

        self._user_filter.action_args = orjson.dumps(action_args).decode("utf-8")  # type: ignore
        AppConfig.write_model_to_db(self._user_filter)
