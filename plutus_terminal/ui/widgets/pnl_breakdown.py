"""Wdiget to display PnL breakdown."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    QEvent,
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

    from PySide6.QtGui import QEnterEvent, QMouseEvent


class PnlBreakdown(QWidget):
    """Pnl breakdown widget."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._tooltip_content = ""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.pnl_label = QLabel(self)
        self.pnl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pnl_label.setObjectName("pnl")
        self._main_layout.addWidget(self.pnl_label)
        self.setLayout(self._main_layout)
        self.setToolTipDuration(0)

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
        funding_fee: Decimal,
        position_fee: Decimal,
        pnl_after_fee: Decimal,
        push_tool_tip: bool = True,
    ) -> None:
        """Set tooltip content."""
        self._tooltip_content = (
            f"PnL: {round(pnl, 3)}<br>"
            f"Funding Fee: {_format_signed_fee(funding_fee)}<br>"
            f"Opening Fee: -{round(position_fee, 3)}<br>"
            f"Closing Fee: -{round(position_fee, 3)}<br><br>"
            f"PnL After Fees: {round(pnl_after_fee, 3)}"
        )
        self.setToolTip(self._tooltip_content)
        if push_tool_tip and self.underMouse():
            QToolTip.showText(self.mapToGlobal(self.rect().center()), self._tooltip_content, self)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Override event to change cursor on hover."""
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        if self._tooltip_content:
            QToolTip.showText(self.mapToGlobal(self.rect().center()), self._tooltip_content, self)
        return super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Override event to reset cursor on leave."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().leaveEvent(event)


def _format_signed_fee(fee: Decimal) -> str:
    """Format fee values with the correct sign semantics for the tooltip."""
    rounded_fee = round(abs(fee), 3)
    if fee < 0:
        return f"+{rounded_fee}"
    return f"-{rounded_fee}"
