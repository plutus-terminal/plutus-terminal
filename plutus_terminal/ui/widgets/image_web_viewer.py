"""Image web viewer widget."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QKeySequence,
    QMouseEvent,
    QPixmap,
    QShortcut,
    QShowEvent,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget


class ImageWebViewer(QLabel):
    """Display images from web that can be zoomed in a modal widget."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize widget shared variables."""
        super().__init__(parent=parent)
        self._pixmap = QPixmap()
        self._max_img_height = 180
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_image(self, image_url: str) -> None:
        """Set image from url."""
        pixmap = QPixmap()
        newtwork_manager = QNetworkAccessManager(self)
        newtwork_manager.finished.connect(self._set_newtwork_image)
        newtwork_manager.get(QNetworkRequest(QUrl(image_url)))

        self.setPixmap(pixmap)

    def _set_newtwork_image(self, reply: QNetworkReply) -> None:
        """Set image pixmap from network reply."""
        image_data = reply.readAll()
        pixmap = QPixmap()
        self._pixmap.loadFromData(image_data)
        height = (
            self._pixmap.height()
            if self._pixmap.height() < self._max_img_height
            else self._max_img_height
        )
        pixmap = self._pixmap.scaled(
            self.parentWidget().size().width(),
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Open model for image when clicked."""
        ImageDisplayModal.show_modal(self._pixmap)
        return super().mousePressEvent(event)


class ImageDisplayModal(QWidget):
    """Display image modal widget."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize modal widget."""
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)

        self._main_layout = QVBoxLayout(self)
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setCursor(Qt.CursorShape.ArrowCursor)

        self.parent().installEventFilter(self)

        self.close_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.close_shortcut.activated.connect(self.close)

        self._main_layout.addWidget(self._image)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_image(self, image_pixmap: QPixmap) -> None:
        """Set image from url."""
        self.resize_image(image_pixmap)

    def resize_image(self, pixmap: QPixmap) -> None:
        """Resize image based on the current widget size."""
        max_size = self.parent().size() * 0.7  # type: ignore
        image_size = max_size if pixmap.height() > max_size.height() else pixmap.size()
        scaled_pixmap = pixmap.scaled(image_size, Qt.AspectRatioMode.KeepAspectRatio)
        self._image.setPixmap(scaled_pixmap)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter resize events.

        Args:
            watched: The object being watched
            event: The event being watched

        Returns:
            bool: True if the event was handled.
        """
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.resize_image(self._image.pixmap())
            self.resize(self.parent().size())  # type: ignore
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Close modal when clicked outside of the image."""
        if not self._image.geometry().contains(event.pos()):
            self.close()
        return super().mousePressEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Raise and resize modal widget."""
        self.raise_()
        self.resize(self.parent().size())  # type: ignore
        return super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Delete widget on close."""
        self.deleteLater()
        return super().closeEvent(event)

    @staticmethod
    def show_modal(image_pixmap: QPixmap) -> None:
        """Show modal widget."""
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                main_window = widget
                break
        if not main_window:
            return
        parent = main_window
        image_display = ImageDisplayModal(parent)
        image_display.set_image(image_pixmap)
        image_display.show()
