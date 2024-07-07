"""Top bar widget."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets
from PySide6.QtCore import Qt


class TopBar(QtWidgets.QWidget):
    """Top bar widget."""

    def __init__(
        self,
        title: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.bar_layout = QtWidgets.QHBoxLayout()
        self.icon = QtWidgets.QLabel()
        self.title = QtWidgets.QLabel(title)
        self.line = QtWidgets.QFrame()

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.bar_layout.setContentsMargins(0, 0, 0, 0)

        self.icon.setMinimumHeight(35)
        self.title.setObjectName("title")
        self.title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        self.line.setObjectName("divisor")
        self.line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

    def _setup_layout(self) -> None:
        """Configure layout."""
        self.bar_layout.addWidget(self.icon)
        self.bar_layout.addWidget(self.title)
        self.bar_layout.addStretch()

        self.setLayout(self.main_layout)
        self.main_layout.addLayout(self.bar_layout)
        self.main_layout.addWidget(self.line)
        self.main_layout.addSpacing(10)

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        """Add widget to bar_layout."""
        self.bar_layout.addWidget(widget)
