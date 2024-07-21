"""Spin Box that holds Decimal values."""

from decimal import Decimal
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets


class DecimalSpinBox(QtWidgets.QDoubleSpinBox):
    """Double spin box."""

    decimalValueChanged = QtCore.Signal(Decimal)  # noqa: N815

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.
        """
        self._current_decimal: Decimal = Decimal(0)
        self._maximum_decimal: Decimal = Decimal(100_000_000_000)
        self._minimum_decimal: Decimal = Decimal(-100_000_000_000)
        super().__init__(*args, **kwargs)
        self.setGroupSeparatorShown(True)
        self.setMaximum(self._maximum_decimal)
        self.setMinimum(self._minimum_decimal)
        self.setDecimals(8)
        self.valueChanged.connect(self._on_value_changed)

    def value(self) -> Decimal:  # type: ignore
        """Get current value.

        Returns:
            Decimal: Current value.
        """
        return self._current_decimal

    def setValue(self, value: Decimal) -> None:  # type: ignore
        """Set value.

        Args:
            value (Decimal): Value to set.
        """
        self._current_decimal = value
        self.decimalValueChanged.emit(value)
        self.blockSignals(True)
        super().setValue(float(value))
        self.blockSignals(False)

    def setMaximum(self, max_value: Decimal) -> None:  # type: ignore
        """Set maximum.

        Args:
            max_value (Decimal): Maximum value.
        """
        self._maximum_decimal = max_value
        return super().setMaximum(float(max_value))

    def maximum(self) -> Decimal:  # type: ignore
        """Get maximum.

        Returns:
            Decimal: Maximum value.
        """
        return self._maximum_decimal

    def setMinimum(self, min_value: Decimal) -> None:  # type: ignore
        """Set minimum.

        Args:
            min_value (Decimal): Minimum value.
        """
        self._minimum_decimal = min_value
        return super().setMinimum(float(min_value))

    def minimum(self) -> Decimal:  # type: ignore
        """Get minimum.

        Returns:
            Decimal: Minimum value.
        """
        return self._minimum_decimal

    def setRange(self, min_value: Decimal, max_value: Decimal) -> None:  # type: ignore
        """Set range.

        Args:
            min_value (Decimal): Minimum value.
            max_value (Decimal): Maximum value.
        """
        self._minimum_decimal = min_value
        self._maximum_decimal = max_value
        return super().setRange(float(min_value), float(max_value))

    def _on_value_changed(self, value: float) -> None:
        """On value changed."""
        self._current_decimal = Decimal(value)
        if self._current_decimal > self._maximum_decimal:
            self._current_decimal = self._maximum_decimal
        if self._current_decimal < self._minimum_decimal:
            self._current_decimal = self._minimum_decimal
        self.decimalValueChanged.emit(self._current_decimal)


class DecimalSpinBoxWithButton(DecimalSpinBox):
    """Decimal spin box with button."""

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
        self.setMinimum(Decimal(0))

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
