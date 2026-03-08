"""PnL cell adapter used by the positions table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plutus_terminal.ui.widgets.pnl_breakdown import PnlBreakdown

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from plutus_terminal.core.exchange.types import PerpsPosition, PnlDetails


class PositionPnlCell(PnlBreakdown):
    """Pnl widget with a positions-table-focused API."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._position: PerpsPosition | None = None

    def set_position(self, position: PerpsPosition) -> None:
        """Track the position associated with this cell."""
        self._position = position

    def set_pnl_details(self, pnl_details: PnlDetails) -> None:
        """Update the cell from calculated pnl details."""
        self.set_pnl(
            pnl_details["pnl_usd_after_fees"],
            pnl_details["pnl_percentage_after_fees"],
        )
        self.set_tooltip_content(
            pnl_details["pnl_usd_before_fees"],
            pnl_details["funding_fee_usd"],
            pnl_details["opening_fee_usd"],
            pnl_details["closing_fee_usd"] if pnl_details.get("show_closing_fee", True) else None,
            pnl_details["pnl_usd_after_fees"],
            funding_fee_included=pnl_details.get("funding_fee_included_in_pnl", False),
            opening_fee_included=pnl_details.get("opening_fee_included_in_pnl", False),
            labels=(
                pnl_details.get("pnl_label", "PnL"),
                pnl_details.get("net_pnl_label", "PnL After Fees"),
            ),
            show_closing_fee=pnl_details.get("show_closing_fee", True),
        )
