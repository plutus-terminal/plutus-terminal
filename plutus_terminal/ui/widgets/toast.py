"""Toaster Widget."""

from enum import Enum
import logging
import os
from typing import ClassVar, Optional

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QCursor,
    QPixmap,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from plutus_terminal.core.config import CONFIG

LOGGER = logging.getLogger(__name__)


class ToastType(Enum):
    """Toaster type enum."""

    MESSAGE = "message"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Toast(QFrame):
    """Toast Message widget for top of screen."""

    _toasts_win: ClassVar[dict] = {}
    _toasts_desktop: ClassVar[dict] = {}
    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None, desktop: bool = False) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self.parent_rect = QRect()
        self._desktop = desktop

        self._main_layout = QVBoxLayout(self)
        self._close_button = QToolButton()
        self._terminal_button = QToolButton()
        self._desktop_label = QLabel()
        self._pin_button = QToolButton()
        self._button_layout = QHBoxLayout()
        self._message_widget = QWidget()
        self._id = os.urandom(8)

        self._timer = QTimer()
        self._margin = 10
        self._toast_distance = 5

        self._setup_widgets()
        self._setup_layout()

    def add_message_widget(self, message_widget: QWidget) -> None:
        """Add message widget."""
        self._message_widget = message_widget
        self._main_layout.addWidget(self._message_widget)

    def _setup_widgets(self) -> None:
        """Configure internal widgets."""
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.BypassWindowManagerHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )

        if self.parent():
            # we have a parent, install an eventFilter so that when it's resized
            # the notification will be correctly moved to the right corner
            self.parent().installEventFilter(self)

        self._pin_button.setIcon(QPixmap(":/icons/pushpin_icon"))
        self._pin_button.setAutoRaise(True)
        self._pin_button.setToolTip("Pin toask and prevent to auto close")
        self._pin_button.clicked.connect(self._pin_toast)

        self._close_button.setIcon(QPixmap(":/icons/close_icon"))
        self._close_button.setAutoRaise(True)
        self._close_button.setToolTip("Close toast")
        self._close_button.clicked.connect(self.close)

        if self._desktop:
            self._terminal_button.setIcon(QPixmap(":/icons/terminal_icon"))
            self._terminal_button.setAutoRaise(True)
            self._terminal_button.setToolTip("Open plutus terminal")
            self._terminal_button.clicked.connect(self._open_main_window)

            self._desktop_label.setText("Plutus Terminal")
            self._desktop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._desktop_label.setObjectName("title")

        self._timer.timeout.connect(self.close)

    def _setup_layout(self) -> None:
        """Configure layout."""
        if self._desktop:
            self._button_layout.addWidget(self._terminal_button)
            self._button_layout.addStretch()
            self._button_layout.addWidget(self._desktop_label)

        self._button_layout.addStretch()
        self._button_layout.addWidget(self._pin_button)
        self._button_layout.addWidget(self._close_button)
        self._main_layout.addLayout(self._button_layout)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter resize events.

        Args:
            watched: The object being watched
            event: The event being watched

        Returns:
            bool: True if the event was handled.
        """
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.parent_rect = self.parent().rect()  # type: ignore
            self.adjust_position()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Adjust position on resize."""
        self.adjust_position()
        return super().resizeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Delete widget on close."""
        self._timer.stop()
        try:
            if self._desktop:
                del Toast._toasts_desktop[self._id]
            else:
                del Toast._toasts_win[self._id]
        except KeyError:
            LOGGER.warning("Toast %s not found", self._id)

        event.accept()

        existent_toasts = (
            list(Toast._toasts_desktop.values())
            if self._desktop
            else list(Toast._toasts_win.values())
        )

        for toast in existent_toasts:
            toast.adjust_position()

    def showEvent(self, event: QShowEvent) -> None:
        """Start time on show."""
        self.adjustSize()
        self.adjust_position(add_event=True)
        self._timer.start()
        self.raise_()
        return super().showEvent(event)

    def adjust_position(self, add_event: bool = False) -> None:
        """Move the toast to corner of parent rect and adjust for multiple messages."""
        geometry = self.geometry()

        offset = 0

        existent_toasts = (
            list(Toast._toasts_desktop.values())
            if self._desktop
            else list(Toast._toasts_win.values())
        )

        toasts = reversed(existent_toasts) if add_event else existent_toasts

        for toast in toasts:
            if toast is not self:
                offset += toast.geometry().height() + self._toast_distance
            elif not add_event and self:
                break

        match CONFIG.get_gui_settings("toast_position"):
            case "top_left":
                geometry.moveTopLeft(
                    self.parent_rect.topLeft() + QPoint(self._margin, self._margin),
                )
            case "top_right":
                geometry.moveTopRight(
                    self.parent_rect.topRight() + QPoint(-self._margin, self._margin),
                )
            case "bottom_left":
                geometry.moveBottomLeft(
                    self.parent_rect.bottomLeft() + QPoint(self._margin, -self._margin - offset),
                )
            case "bottom_right":
                geometry.moveBottomRight(
                    self.parent_rect.bottomRight() + QPoint(-self._margin, -self._margin - offset),
                )

        self.setGeometry(geometry)

    def _open_main_window(self) -> None:
        """Open main window."""
        self.close()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                main_window = widget
                main_window.show()

    def _pin_toast(self) -> None:
        """Pin toast and prevent to auto close."""
        if self._timer.isActive():
            self.setObjectName("pinned")
            self._pin_button.setIcon(QPixmap(":/icons/unpin_icon"))
            self._timer.stop()
        else:
            self.setObjectName("")
            self._pin_button.setIcon(QPixmap(":/icons/pushpin_icon"))
            self._timer.start()
        self.style().polish(self)

    @staticmethod
    def show_message(
        message: str,
        timeout: int = 10000,
        desktop: bool = False,
        type_: ToastType = ToastType.MESSAGE,
    ) -> bytes:
        """Show Toast message.

        Args:
            message (str): Message to show.
            timeout (int, optional): Timeout in milliseconds. Defaults to 10000.
            desktop (bool, optional): Show on desktop. Defaults to False.
            type_ (ToastType, optional): Toast type. Defaults to ToastType.MESSAGE.

        Returns:
            bytes: Toast ID.
        """
        message_label = QLabel(message)
        message_label.setTextFormat(Qt.TextFormat.RichText)
        message_label.setOpenExternalLinks(True)
        return Toast.show_widget(message_label, timeout, desktop, type_)

    @staticmethod
    def update_message(
        toast_id: bytes,
        message: str,
        type_: ToastType,
        desktop: bool = False,
    ) -> None:
        """Update toast message.

        Args:
            toast_id (bytes): Toast ID.
            message (str): Message to show.
            type_ (ToastType): Toast type.
            desktop (bool, optional): Show on desktop. Defaults to False.
        """
        if desktop:
            toast = Toast._toasts_desktop.get(toast_id, False)
        else:
            toast = Toast._toasts_win.get(toast_id, False)

        if not toast:
            return
        toast._message_widget.setText(message)  # noqa: SLF001
        toast._timer.start()  # noqa: SLF001
        toast.setProperty("class", type_.value)
        toast.style().polish(toast)
        toast.resize(toast.sizeHint())
        toast.adjust_position()

    @staticmethod
    def show_widget(
        message_widget: QWidget,
        timeout: int = 10000,
        desktop: bool = False,
        type_: ToastType = ToastType.MESSAGE,
    ) -> bytes:
        """Show toast widget.

        Args:
            message_widget (QWidget): Message widget to show.
            timeout (int, optional): Timeout in milliseconds. Defaults to 10000.
            desktop (bool, optional): Show on desktop. Defaults to False.
            type_ (ToastType, optional): Toast type. Defaults to ToastType.MESSAGE.

        Returns:
            bytes: Toast ID.
        """
        if desktop:
            # Setup to show on desktop
            toast = Toast(None, desktop=True)
            current_screen = QApplication.primaryScreen()

            # Use cursor for window reference
            reference = QRect(QCursor.pos() - QPoint(1, 1), QSize(3, 3))

            max_area = 0
            for screen in QApplication.screens():
                screen_rect = screen.geometry().intersected(reference)
                area = screen_rect.width() * screen_rect.height()
                if area > max_area:
                    max_area = area
                    current_screen = screen
                    break
            parent_rect = current_screen.availableGeometry()
        else:
            # Setup to show on top of main window
            main_window = None
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QMainWindow):
                    main_window = widget
                    break
            if not main_window:
                msg = "No main window found"
                raise ValueError(msg)
            parent = main_window
            toast = Toast(parent)
            parent_rect = parent.rect()

        # Store toast in memory depending of type
        if desktop:
            Toast._toasts_desktop[toast._id] = toast  # noqa: SLF001
        else:
            Toast._toasts_win[toast._id] = toast  # noqa: SLF001

        toast._timer.setInterval(timeout)  # noqa: SLF001

        # Add message to toast
        toast.add_message_widget(message_widget)
        toast.setProperty("class", type_.value)

        toast.parent_rect = parent_rect
        # Extra flag to prevent taskbar icon
        if desktop:
            toast.setWindowFlag(Qt.WindowType.Tool)
        toast.show()
        return toast._id  # noqa: SLF001
