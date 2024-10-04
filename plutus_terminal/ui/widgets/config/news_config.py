"""Widget to control news configuration."""

from __future__ import annotations

from functools import partial
from typing import Optional

import keyring
import orjson
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtMultimedia import QSoundEffect

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.db.models import UserFilter
from plutus_terminal.core.news.filter._actions import FILTER_ACTIONS_MAP
from plutus_terminal.core.news.filter.types import ActionType, FilterType
from plutus_terminal.core.news.phoenix_news import PHOENIX_KEY_NAME
from plutus_terminal.core.news.tree_news import TREE_KEY_NAME
from plutus_terminal.ui.ui_utils import list_resources_from_prefix
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar


class NewsConfig(QtWidgets.QWidget):
    """Widget to control news configuration."""

    update_filters = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)

        self._main_layout = QtWidgets.QVBoxLayout()

        self._news_source_bar = TopBar("News Source API Keys")
        self._tree_box = QtWidgets.QGroupBox("TreeOfAlpha API Key")
        self._tree_box_layout = QtWidgets.QVBoxLayout()
        self._tree_text_label = QtWidgets.QLabel()
        self._tree_input = QtWidgets.QLineEdit()
        self._phoenix_box = QtWidgets.QGroupBox("Phoenix API Key")
        self._phoenix_box_layout = QtWidgets.QVBoxLayout()
        self._phoenix_text_label = QtWidgets.QLabel()
        self._phoenix_input = QtWidgets.QLineEdit()

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

    def _setup_widgets(self) -> None:
        """Config widgets."""
        self._tree_text_label.setWordWrap(True)
        self._tree_text_label.setOpenExternalLinks(True)
        self._tree_text_label.setText(
            """Add your TreeOfAlpha API key bellow if you are a paid subscriber.<br>"""
            """To get your API key, go to """
            """<a href="https://news.treeofalpha.com/api/api_key """
            """style="color:rgb(80, 210, 180)">"""
            """https://news.treeofalpha.com/api/api_key</a>""",
        )
        current_tree_key = keyring.get_password(
            "plutus-terminal:news-source",
            TREE_KEY_NAME,
        )
        if current_tree_key:
            self._tree_input.setText(current_tree_key)
        else:
            self._tree_input.setPlaceholderText(
                "Enter your TreeOfAlpha API key here...",
            )

        self._phoenix_text_label.setWordWrap(True)
        self._phoenix_text_label.setText(
            """Add your PhoenixNews API key bellow if you are a paid subscriber.<br>"""
            """To get your API key, go to """
            """<a href="https://phoenixnews.io", style="color:rgb(80, 210, 180)">"""
            """https://phoenixnews.io</a>""",
        )
        self._phoenix_text_label.setOpenExternalLinks(True)
        current_phoenix_key = keyring.get_password(
            "plutus-terminal:news-source",
            PHOENIX_KEY_NAME,
        )
        if current_phoenix_key:
            self._phoenix_input.setText(current_phoenix_key)
        else:
            self._phoenix_input.setPlaceholderText("Enter your Phoenix API key here...")

        self._tree_input.editingFinished.connect(
            partial(self.record_news_source_key, TREE_KEY_NAME),
        )
        self._phoenix_input.editingFinished.connect(
            partial(self.record_news_source_key, PHOENIX_KEY_NAME),
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

        user_filters = CONFIG.get_all_user_filters()
        for user_filter in user_filters:
            if int(user_filter.filter_type) == FilterType.KEYWORD_MATCHING:  # type: ignore
                self._keyword_matching_layout.addWidget(KeywordMatchingWidget(user_filter))
            if int(user_filter.filter_type) == FilterType.DATA_MATCHING:  # type: ignore
                self._data_matching_layout.addWidget(DataMatchingWidget(user_filter))

    def _setup_layout(self) -> None:
        """Config layout."""
        self._main_layout.addWidget(self._news_source_bar)
        self._tree_box_layout.addWidget(self._tree_text_label)
        self._tree_box_layout.addWidget(self._tree_input)
        self._tree_box.setLayout(self._tree_box_layout)
        self._main_layout.addWidget(self._tree_box)

        self._phoenix_box_layout.addWidget(self._phoenix_text_label)
        self._phoenix_box_layout.addWidget(self._phoenix_input)
        self._phoenix_box.setLayout(self._phoenix_box_layout)
        self._main_layout.addWidget(self._phoenix_box)

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

    def record_news_source_key(self, news_source: str) -> None:
        """Record the news source API key in keyring.

        Args:
            news_source: name of the news source,
        """
        text_source = {
            TREE_KEY_NAME: self._tree_input.text(),
            PHOENIX_KEY_NAME: self._phoenix_input.text(),
        }
        keyring.set_password(
            "plutus-terminal:news-source",
            news_source,
            text_source[news_source],
        )
        Toast.show_message(
            "News source API key saved successfully!",
            type_=ToastType.SUCCESS,
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
        user_filters = CONFIG.get_all_user_filters()
        for user_filter in user_filters:
            if int(user_filter.filter_type) == FilterType.KEYWORD_MATCHING:  # type: ignore
                self._keyword_matching_layout.insertWidget(
                    self._keyword_matching_layout.count() - 1,
                    KeywordMatchingWidget(user_filter),
                )
            if int(user_filter.filter_type) == FilterType.DATA_MATCHING:  # type: ignore
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

        self.update_filters.emit()


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
                "QPushButton#buttonColor {background-color: %s;}" % self._color.name(),
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
            CONFIG.delete_user_filter(self._user_filter.id)  # type: ignore
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
        CONFIG.write_model_to_db(self._user_filter)


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
        CONFIG.write_model_to_db(self._user_filter)
