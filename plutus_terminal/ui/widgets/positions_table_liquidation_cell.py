"""Liquidation price cell used by the positions table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from plutus_terminal.ui import ui_utils

if TYPE_CHECKING:
    from decimal import Decimal


class LiquidationPriceCell(QWidget):
    """Widget to display liquidation price without cell flicker."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize widget with stable text state."""
        super().__init__(parent)
        self._price_label = QLabel("--", self)
        self._price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self._price_label)

    def set_price(self, price: Decimal | None) -> None:
        """Update shown liquidation price while preserving prior value on missing input."""
        if price is None:
            return

        minimal_digits = ui_utils.get_minimal_digits(float(price), 3)
        self._price_label.setText(f"<span style='color:orange'>${price:,.{minimal_digits}f}</span>")
