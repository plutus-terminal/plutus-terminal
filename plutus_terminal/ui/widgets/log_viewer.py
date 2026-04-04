"""Module to display log data."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from plutus_terminal.log_utils import LOG_PATH, LOGS_FOLDER_PATH
from plutus_terminal.ui.widgets.toast import Toast, ToastType


class LogViewer(QtWidgets.QDialog):
    """Log viewer dialog to display log data."""

    _TAIL_INTERVAL_MS = 500
    _BUTTON_MIN_HEIGHT = 35

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize dialog."""
        super().__init__(parent)
        self._log_path = LOG_PATH
        self._last_position = 0
        self._tail_paused = False

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(2, 2, 2, 2)

        self._status_label = QtWidgets.QLabel()
        self._status_label.setObjectName("subText")
        self._status_label.setWordWrap(True)

        self._log_view = QtWidgets.QPlainTextEdit(self)
        self._log_view.setReadOnly(True)

        self._tail_timer = QtCore.QTimer(self)
        self._tail_timer.timeout.connect(self._poll_log_file)

        self._button_layout = QtWidgets.QHBoxLayout()
        self._auto_scroll_checkbox = QtWidgets.QCheckBox("Auto-scroll")
        self._auto_scroll_checkbox.setChecked(True)
        self._toggle_tail_button = QtWidgets.QPushButton("Pause Tail")
        self._toggle_tail_button.clicked.connect(self._toggle_tail)
        self._clear_view_button = QtWidgets.QPushButton("Clear View")
        self._clear_view_button.clicked.connect(self._clear_view)
        self._open_log_folder_button = QtWidgets.QPushButton("Open Log Folder")
        self._open_log_folder_button.clicked.connect(self._open_log_folder)
        self._copy_log_path_button = QtWidgets.QPushButton("Copy Log Path")
        self._copy_log_path_button.clicked.connect(self._copy_log_path)
        self._copy_log_content_button = QtWidgets.QPushButton("Copy Log Content")
        self._copy_log_content_button.clicked.connect(self._copy_log_content)

        self._setup_layout()
        self.setWindowTitle(f"Log Viewer - {self._log_path}")
        self.setWindowIcon(self._resolve_window_icon())
        self.setMinimumSize(900, 600)

    def _resolve_window_icon(self) -> QtGui.QIcon:
        """Return the preferred window icon with safe fallbacks."""
        icon = QtGui.QIcon(QtGui.QPixmap(":/icons/plutus_icon"))
        if not icon.isNull():
            return icon

        app_icon = QtWidgets.QApplication.windowIcon()
        if not app_icon.isNull():
            return app_icon

        return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon)

    def _setup_layout(self) -> None:
        """Configure the dialog layout."""
        for button in (
            self._toggle_tail_button,
            self._clear_view_button,
            self._open_log_folder_button,
            self._copy_log_path_button,
            self._copy_log_content_button,
        ):
            button.setMinimumHeight(self._BUTTON_MIN_HEIGHT)
        self._auto_scroll_checkbox.setMinimumHeight(self._BUTTON_MIN_HEIGHT)

        self._button_layout.addWidget(self._auto_scroll_checkbox)
        self._button_layout.addWidget(self._toggle_tail_button)
        self._button_layout.addWidget(self._clear_view_button)
        self._button_layout.addStretch()
        self._button_layout.addWidget(self._open_log_folder_button)
        self._button_layout.addWidget(self._copy_log_path_button)
        self._button_layout.addWidget(self._copy_log_content_button)

        self._main_layout.addWidget(self._status_label)
        self._main_layout.addWidget(self._log_view)
        self._main_layout.addLayout(self._button_layout)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Load and start tailing when the dialog becomes visible."""
        super().showEvent(event)
        self._load_log()
        self._start_tailing()
        self.raise_()
        self.activateWindow()

    def open_dialog(self) -> None:
        """Show the viewer and keep it in front of its parent window."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        """Stop background polling while the dialog is hidden."""
        self._stop_tailing()
        super().hideEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Stop tailing before closing."""
        self._stop_tailing()
        super().closeEvent(event)

    def _start_tailing(self) -> None:
        """Start the periodic tail poller."""
        if not self._tail_paused:
            self._tail_timer.start(self._TAIL_INTERVAL_MS)
            self._set_status("Live tail active.")

    def _stop_tailing(self) -> None:
        """Stop the periodic tail poller."""
        if self._tail_timer.isActive():
            self._tail_timer.stop()

    def _set_status(self, message: str) -> None:
        """Show the current viewer status."""
        self._status_label.setText(f"{message} File: {self._log_path}")

    def _load_log(self) -> None:
        """Load the current log file contents."""
        if not self._log_path.exists():
            self._last_position = 0
            self._log_view.setPlainText("Log file not found yet.")
            self._set_status("Waiting for log file.")
            return

        with self._log_path.open(encoding="utf-8", errors="ignore") as log_file:
            content = log_file.read()

        self._log_view.setPlainText(content)
        self._last_position = self._log_path.stat().st_size
        if self._auto_scroll_checkbox.isChecked():
            self._scroll_to_end()
        self._set_status("Live tail active.")

    def _poll_log_file(self) -> None:
        """Append new log content while the viewer stays open."""
        if self._tail_paused:
            return
        if not self._log_path.exists():
            self._set_status("Waiting for log file.")
            return

        current_size = self._log_path.stat().st_size
        if current_size < self._last_position:
            self._load_log()
            self._set_status("Log rotated or truncated. Reloaded and tailing.")
            return
        if current_size == self._last_position:
            return

        with self._log_path.open(encoding="utf-8", errors="ignore") as log_file:
            log_file.seek(self._last_position)
            chunk = log_file.read()

        self._last_position = current_size
        if not chunk:
            return

        cursor = self._log_view.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self._log_view.setTextCursor(cursor)
        if self._auto_scroll_checkbox.isChecked():
            self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        """Scroll the log view to the end."""
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _toggle_tail(self) -> None:
        """Pause or resume log tailing."""
        self._tail_paused = not self._tail_paused
        if self._tail_paused:
            self._stop_tailing()
            self._toggle_tail_button.setText("Resume Tail")
            self._set_status("Live tail paused.")
            return

        self._toggle_tail_button.setText("Pause Tail")
        self._start_tailing()
        self._poll_log_file()

    def _clear_view(self) -> None:
        """Clear the current log view without touching the file."""
        self._log_view.clear()
        self._set_status("View cleared. Live tail will append new lines.")

    def _open_log_folder(self) -> None:
        """Open the folder that contains the current log file."""
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(LOGS_FOLDER_PATH)))

    def _copy_log_path(self) -> None:
        """Copy the log path to the clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(str(self._log_path))
        Toast.show_message(
            "Log path copied to clipboard",
            type_=ToastType.SUCCESS,
            desktop=True,
        )

    def _copy_log_content(self) -> None:
        """Copy log content."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self._log_view.toPlainText())
        Toast.show_message(
            "Log content copied to clipboard",
            type_=ToastType.SUCCESS,
            desktop=True,
        )

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Customize navigation keys."""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        elif event.key() == QtCore.Qt.Key.Key_J:
            self._log_view.moveCursor(QtGui.QTextCursor.MoveOperation.Down)
        elif event.key() == QtCore.Qt.Key.Key_K:
            self._log_view.moveCursor(QtGui.QTextCursor.MoveOperation.Up)
        else:
            super().keyPressEvent(event)
