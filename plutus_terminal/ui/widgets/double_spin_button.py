"""Spin BDecimal values."""

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class DoubleSpinBoxWithButton(QtWidgets.QDoubleSpinBox):
    """Double spin box with button."""

    buttonClicked = QtCore.Signal()  # noqa: N815

    def __init__(
        self,
        button_text: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self.button = QtWidgets.QPushButton(button_text, self)
        self.button.setFixedWidth(50)
        self.button.setObjectName("spinButton")
        self.button.clicked.connect(self.buttonClicked.emit)

        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setMinimum(0)
        self.setMaximum(1_000_000_000)
        self.setDecimals(8)
        self.setGroupSeparatorShown(True)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Adjust button position on resize.

        Button will be placed on the right side of the spin box with a distance
        of 5% of the border.
        """
        super().resizeEvent(event)
        self.update_button_position()

    def update_button_position(self) -> None:
        """Update button position."""
        button_size = self.button.size()
        self.button.move(
            self.width() - button_size.width() - 10,
            (self.height() - button_size.height()) // 2,
        )

    def show(self) -> None:
        """Override show method to update button position."""
        super().show()
        self.update_button_position()
