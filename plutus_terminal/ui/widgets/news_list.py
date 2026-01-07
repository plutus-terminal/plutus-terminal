"""New list widget."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtMultimedia import QSoundEffect
from qasync import asyncSlot

from plutus_terminal.ui.ui_utils import list_resources_from_prefix
from plutus_terminal.ui.widgets.news_widget import NewsWidget
from plutus_terminal.ui.widgets.toast import Toast
from plutus_terminal.ui.widgets.top_bar_widget import TopBar
from plutus_terminal.controller.news_list_controller import NewsListController

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.types_ import NewsData


class NewsList(QtWidgets.QWidget):
    """News list widget.

    Acts like a news factory and handles news items.
    """

    refresh_news = Signal()

    def __init__(
        self,
        ui_controller: UIController,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(parent=parent)
        self.controller = NewsListController(ui_controller)

        self._main_layout = QtWidgets.QVBoxLayout()

        self.top_bar = TopBar("News Feed")
        self._top_bar_show_images = QtWidgets.QRadioButton()
        self._top_bar_notifications = QtWidgets.QRadioButton()
        self._top_bar_max_news = QtWidgets.QComboBox()

        self._scroll_area = QtWidgets.QScrollArea()
        self._content_area = QtWidgets.QWidget()
        self._scroll_layout = QtWidgets.QVBoxLayout()

        self._sfxs: dict[str, QSoundEffect] = {}

        self._selected_news_widget: NewsWidget | None = None

        self._load_sfxs()
        self._setup_widgets()
        self._connect_signals()
        self._setup_layout()
        self._setup_shorcuts()

        self.controller.connect_signals()

    def _load_sfxs(self) -> None:
        """Load sound effects in memory."""
        for sfx_name in list_resources_from_prefix("sfx"):
            sfx_path = f":/sfx/{sfx_name}"
            sfx = QSoundEffect()
            sfx.setSource(QUrl.fromLocalFile(sfx_path))
            self._sfxs[sfx_path] = sfx

    def _setup_widgets(self) -> None:
        """Create internal widgets."""
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
        )

        self.top_bar.icon.setPixmap(QPixmap(":/icons/news_feed_icon"))

        self._top_bar_show_images.setAutoExclusive(False)
        self._top_bar_show_images.setIcon(QPixmap(":/icons/gallery_icon"))
        self._top_bar_show_images.setChecked(
            self.controller.app_config.get_gui_settings("news_show_images"),  # type: ignore
        )
        self._top_bar_show_images.setToolTip("Show Images")

        self._top_bar_notifications.setAutoExclusive(False)
        self._top_bar_notifications.setChecked(
            self.controller.app_config.get_gui_settings("news_desktop_notifications"),  # type: ignore
        )
        if self._top_bar_notifications.isChecked():
            self._top_bar_notifications.setIcon(QPixmap(":/icons/notification_on"))
        else:
            self._top_bar_notifications.setIcon(QPixmap(":/icons/notification_off"))
        self._top_bar_notifications.setToolTip("Enable Desktop Notifications")

        self._top_bar_max_news.addItems(["25 results", "50 results", "100 results", "200 results"])

        self.top_bar.add_widget(self._top_bar_show_images)
        self.top_bar.add_widget(self._top_bar_notifications)
        self.top_bar.add_widget(self._top_bar_max_news)

        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._top_bar_show_images.toggled.connect(
            partial(self.controller.app_config.set_gui_settings, "news_show_images")
        )
        self._top_bar_notifications.toggled.connect(
            partial(self.controller.app_config.set_gui_settings, "news_desktop_notifications")
        )

        self._top_bar_max_news.currentIndexChanged.connect(
            self.update_max_news,
        )
        self._scroll_area.verticalScrollBar().rangeChanged.connect(
            lambda: self._show_widget_at_top(self._selected_news_widget),
        )

        self.controller.app_config.news_show_images_changed.connect(self.show_images_toggled)
        self.controller.app_config.news_desktop_notifications_changed.connect(self.notifications_toggled)

        self.controller.add_news_widget.connect(self.add_news_widget)
        self.controller.clear_list.connect(self.clear_list)
        # self.controller.update_trade_buttons.connect(self.update_news_trade_buttons)
        # Actually NewsWidget listens to controller signals, so update_news_trade_buttons might not be needed in NewsList anymore?
        # NewsWidget connects `self.controller.update_trade_buttons.connect(self.update_trade_buttons)`
        # And NewsListController emits `update_trade_buttons`. But NewsListController creates NewsController.
        # Wait, NewsListController emits a signal `update_trade_buttons`.
        # But each NewsWidget has its own NewsController.
        # The NewsListController should probably tell active NewsControllers to update trade buttons?
        # Or simply rely on `app_config` signals inside NewsController?
        # In the previous `NewsList` code, it iterated over widgets and called `update_trade_buttons`.
        # In `NewsWidget` refactor, I added `self.controller.update_trade_buttons.connect(self.update_trade_buttons)`.
        # So if NewsController emits it, the widget updates.
        # But NewsController needs to know when to emit it.
        # Ah, NewsListController listens to app_config and emits its own signal.
        # But NewsWidget is connected to NewsController, not NewsListController.
        # So NewsController should listen to app_config changes too.
        # Let's check NewsController again.

        # In NewsController:
        # It has `update_trade_buttons = Signal()`.
        # But it doesn't seem to connect `app_config` signals to this signal or a handler.
        # I should fix NewsController to listen to app_config changes.

    def _setup_layout(self) -> None:
        """Configure layouts."""
        self._main_layout.addWidget(self.top_bar)
        self._scroll_area.setWidget(self._content_area)
        self._content_area.setLayout(self._scroll_layout)
        self._main_layout.addWidget(self._scroll_area)

        self.setLayout(self._main_layout)

    def _setup_shorcuts(self) -> None:
        """Configure shortcuts."""
        self._reset_scroll_shortcut = QShortcut(QKeySequence("q"), self)
        self._reset_scroll_shortcut.activated.connect(self._reset_scroll_to_top)

        self._step_up_shortcut = QShortcut(QKeySequence("w"), self)
        self._step_up_shortcut.activated.connect(
            self._step_widget_up,
        )

        self._set_down_shortcut = QShortcut(QKeySequence("s"), self)
        self._set_down_shortcut.activated.connect(self._step_widget_down)

        self._open_link_shortcut = QShortcut(QKeySequence("space"), self)
        self._open_link_shortcut.activated.connect(self._open_link)

    def _reset_scroll_to_top(self) -> None:
        """Reset the scroll position to 0."""
        if self._selected_news_widget is None:
            self._selected_news_widget = self._scroll_layout.itemAt(0).widget()  # type: ignore
        self._show_widget_index_at_top(0)

    def _step_widget_up(self) -> None:
        """Move scroll bar 1 news widget up."""
        if self._selected_news_widget is None:
            self._selected_news_widget = self._scroll_layout.itemAt(0).widget()  # type: ignore
        current_index = self._scroll_layout.indexOf(self._selected_news_widget)  # type: ignore
        self._show_widget_index_at_top(current_index - 1)

    def _step_widget_down(self) -> None:
        """Move scroll bar 1 news widget down."""
        if self._selected_news_widget is None:
            self._selected_news_widget = self._scroll_layout.itemAt(0).widget()  # type: ignore
        current_index = self._scroll_layout.indexOf(self._selected_news_widget)  # type: ignore
        self._show_widget_index_at_top(current_index + 1)

    def _show_widget_index_at_top(self, index: int) -> None:
        """Move scroll area to show widget at the top."""
        # Ensure the index is within valid range
        if index < 0 or index >= self._scroll_layout.count():
            return

        news_widget = self._scroll_layout.itemAt(index).widget()
        if not isinstance(news_widget, NewsWidget):
            return
        self._select_news_widget(news_widget)

        # Calculate the cumulative height of all widgets up to the selected one
        cumulative_height = 0
        for i in range(index):
            widget = self._scroll_layout.itemAt(i).widget()
            if widget.isVisible():  # Consider only visible widgets
                cumulative_height += widget.height()  # Use actual height

            # Add spacing after each widget except the last one
            if i < index - 1:
                cumulative_height += self._scroll_layout.spacing()

        # Include top margin of the layout
        cumulative_height += self._scroll_layout.contentsMargins().top()

        # Set the vertical scroll bar's value to the cumulative height
        self._scroll_area.verticalScrollBar().setValue(cumulative_height)

    def _show_widget_at_top(self, news_widget: NewsWidget | None) -> None:
        """Move scroll area to show widget at the top."""
        if news_widget is None:
            return
        self._show_widget_index_at_top(self._scroll_layout.indexOf(news_widget))

    def _select_news_widget(self, news_widget: NewsWidget | None) -> None:
        """Select news widget."""
        if news_widget is None:
            return

        # Ensure there is news selected
        if self._selected_news_widget is not None:
            self._selected_news_widget.set_unselected_style()

        # Select new widget
        self._selected_news_widget = news_widget
        self._selected_news_widget.set_selected_style()  # type: ignore

    def add_news_widget(self, controller: NewsController, display_delay: bool) -> None:
        """Add news widget to the list.

        Args:
            controller (NewsController): News controller.
            display_delay (bool): Whether to display delay.
        """
        self._sfxs[controller.news_data["sfx"]].play()
        if self.controller.app_config.get_gui_settings("news_desktop_notifications"):
            desktop_news = self._create_news_widget(controller, display_delay)
            Toast.show_widget(
                desktop_news,
                timeout=35000,
                desktop=True,
            )

        self._add_news_to_list(controller, display_delay)

    def _create_news_widget(self, controller: NewsController, display_delay: bool) -> NewsWidget:
        """Create news widget.

        Args:
            controller (NewsController): News controller.
            display_delay (bool): Whether to display delay.

        Returns:
            NewsWidget: Created news widget.
        """
        news_widget = NewsWidget(
            controller.news_data,
            controller,
            display_delay=display_delay,
        )
        news_widget.show_images = self.controller.app_config.get_gui_settings("news_show_images") # type: ignore
        news_widget.pair_clicked.connect(self.controller.ui_controller.change_current_pair)
        news_widget.news_clicked.connect(self._show_widget_at_top)
        return news_widget

    def _add_news_to_list(self, controller: NewsController, display_delay: bool) -> None:
        """Add news to list respecting the limit.

        Args:
            controller (NewsController): News controller.
            display_delay (bool): Whether to display delay.
        """
        news_widget = self._create_news_widget(controller, display_delay)

        # If no news is selected, select the new one
        if self._selected_news_widget is None:
            self._selected_news_widget = news_widget
        # If the news is already selected, unselect it and select the new one
        elif self._scroll_layout.indexOf(self._selected_news_widget) == 0:
            self._selected_news_widget.set_unselected_style()
            self._selected_news_widget = news_widget

        # Remove oldest widget if the limit is reached
        self._scroll_area.blockSignals(True)
        if self._scroll_layout.count() > self.controller.max_news:
            old_widget = self._scroll_layout.takeAt(
                self._scroll_layout.count() - 1,
            ).widget()
            if old_widget == self._selected_news_widget:
                self._selected_news_widget = self._scroll_layout.itemAt(
                    self.controller.max_news - 1,
                ).widget()  # type: ignore
            old_widget.deleteLater()
        self._scroll_layout.insertWidget(0, news_widget)
        self._scroll_area.blockSignals(False)

    def clear_list(self) -> None:
        """Clear list."""
        while self._scroll_layout.count():
            old_widget = self._scroll_layout.takeAt(
                self._scroll_layout.count() - 1,
            ).widget()
            old_widget.deleteLater()
        self._selected_news_widget = None

    def _open_link(self) -> None:
        """Open link of selected news in browser."""
        if self._selected_news_widget is None:
            return
        self._selected_news_widget.open_link()

    def show_images_toggled(self, value: bool) -> None:
        """Show images toggled."""
        self._top_bar_show_images.setChecked(value)

        for index in range(self._scroll_layout.count()):
            widget = self._scroll_layout.itemAt(index).widget()
            if isinstance(widget, NewsWidget):
                widget.show_images = value

    def notifications_toggled(self, value: bool) -> None:
        """Notifications toggled."""
        self._top_bar_notifications.setChecked(value)
        if value:
            self._top_bar_notifications.setIcon(QPixmap(":/icons/notification_on"))
        else:
            self._top_bar_notifications.setIcon(QPixmap(":/icons/notification_off"))

    @asyncSlot()
    async def update_max_news(self, max_news_index: int) -> None:
        """Update max news."""
        max_news_text = self._top_bar_max_news.itemText(max_news_index)
        max_news = int(max_news_text.split(" ")[0])
        await self.controller.set_max_news(max_news)

    @asyncSlot()
    async def fill_old_news(self) -> None:
        """Fill old news. Called from somewhere?"""
        await self.controller.fill_old_news()
