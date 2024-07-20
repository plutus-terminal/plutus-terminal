"""Wdiget to display PnL breakdown."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QLabel,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from PySide6.QtGui import QMouseEvent


class PnlBreakdown(QWidget):
    """Pnl breakdown widget."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._tooltip_content = ""
        self._main_layout = QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.pnl_label = QLabel()
        self.pnl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pnl_label.setObjectName("pnl")
        self._main_layout.addWidget(self.pnl_label)
        self.setLayout(self._main_layout)

        self._show_tooltip = False

    def set_pnl(self, usd: Decimal, percent: Decimal) -> None:
        """Set pnl."""
        color = "green" if percent > 0 else "red"
        text_format = (
            f"<span style='color:{color}'>{round(usd, 3)} USD<br>{round(percent, 3)}%</span>"
        )
        self.pnl_label.setText(text_format)

    def set_tooltip_content(
        self,
        pnl: Decimal,
        borrow_fee: Decimal,
        closing_fee: Decimal,
        pnl_after_fee: Decimal,
        push_tool_tip: bool = True,
    ) -> None:
        """Set tooltip content."""
        self._tooltip_content = (
            f"PnL: {round(pnl, 3)}<br>"
            f"Borrow Fee: -{round(borrow_fee, 3)}<br>"
            f"Closing Fee: -{round(closing_fee, 3)}<br><br>"
            f"PnL After Fees: {round(pnl_after_fee, 3)}"
        )
        if self._show_tooltip and push_tool_tip:
            QToolTip.showText(
                self.mapToGlobal(self.rect().center()),
                self._tooltip_content,
            )
        else:
            self.setToolTip(self._tooltip_content)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Override event to show tooltip."""
        if event.button() == Qt.MouseButton.RightButton:
            self._show_tooltip = True
            return None
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Override event to hide tooltip."""
        if event.button() == Qt.MouseButton.RightButton:
            self._show_tooltip = False
            QToolTip.hideText()
            return None
        return super().mouseReleaseEvent(event)
