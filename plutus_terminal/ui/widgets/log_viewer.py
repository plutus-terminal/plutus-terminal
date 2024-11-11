"""Module to display log data."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from plutus_terminal.log_utils import LOG_PATH
from plutus_terminal.ui.widgets.toast import Toast, ToastType


class LogViewer(QtWidgets.QDialog):
    """Log viewer dialog to display log data."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize dialog."""
        super().__init__(parent)
        self._log_path = LOG_PATH

        self._main_layout = QtWidgets.QVBoxLayout()
        self._main_layout.setContentsMargins(2, 2, 2, 2)

        self._log_view = QtWidgets.QPlainTextEdit(self)
        self._log_view.setReadOnly(True)

        self._button_layout = QtWidgets.QHBoxLayout()

        self._button_layout.addStretch()
        self._copy_log_path_button = QtWidgets.QPushButton("Copy Log Path")
        self._copy_log_path_button.clicked.connect(self._copy_log_path)
        self._copy_log_path_button.setMinimumHeight(40)
        self._button_layout.addWidget(self._copy_log_path_button)

        self._copy_log_content_button = QtWidgets.QPushButton("Copy Log Content")
        self._copy_log_content_button.clicked.connect(self._copy_log_content)
        self._copy_log_content_button.setMinimumHeight(40)
        self._copy_log_content_button.setMinimumWidth(
            int(self._copy_log_content_button.sizeHint().width() * 1.05),
        )
        self._copy_log_path_button.setMinimumWidth(
            int(self._copy_log_content_button.sizeHint().width() * 1.05),
        )
        self._button_layout.addWidget(self._copy_log_content_button)

        self._main_layout.addWidget(self._log_view)
        self._main_layout.addLayout(self._button_layout)

        self.setWindowTitle(f"Log Viewer - {self._log_path}")
        self.setMinimumSize(800, 600)
        self.setLayout(self._main_layout)

    def show(self) -> None:
        """Show dialog and refresh log text."""
        self._load_log()
        super().show()

    def _load_log(self) -> None:
        """Load log data."""
        with self._log_path.open() as log_file:
            self._log_view.setPlainText(log_file.read())

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
