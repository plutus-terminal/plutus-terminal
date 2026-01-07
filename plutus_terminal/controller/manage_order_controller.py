"""Controller for ManageOrder Dialog."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from plutus_terminal.core.exchange.types import (
    OrderData,
    PerpsTradeType,
)

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.types_ import PerpsPosition


class ManageOrderController(QObject):
    """Controller for ManageOrder Dialog."""

    update_pnl = Signal(str, str, str, str, str, str)  # pnl_label, pnl_usd_before, funding, pos_fee, pnl_after, pnl_percent
    update_liquidation = Signal(Decimal)
    execute_order_signal = Signal(OrderData)

    def __init__(
        self,
        order_data: OrderData,
        exchange: ExchangeBase,
        associated_position: PerpsPosition | None,
    ) -> None:
        """Initialize controller.

        Args:
            order_data (OrderData): Order data.
            exchange (ExchangeBase): Exchange instance.
            associated_position (PerpsPosition | None): Associated position.
        """
        super().__init__()
        self.order_data = order_data
        self.exchange = exchange
        self.associated_position = associated_position

    def calculate_pnl(self, trigger_price: float) -> None:
        """Calculate and emit PnL updates.

        Args:
            trigger_price (float): Trigger price.
        """
        if self.associated_position is None:
            # Emit empty/default values
            self.update_pnl.emit("--", "", "", "", "", "")
            return

        pnl_details = self.exchange.calculate_pnl(self.associated_position, Decimal(trigger_price))

        self.update_pnl.emit(
            "--", # pnl_label text is set by view, usually just "Est. PnL:"
            f"${pnl_details['pnl_usd_before_fees']:.2f}",
            f"${pnl_details['funding_fee_usd']:.2f}",
            f"${pnl_details['position_fee_usd']:.2f}",
            f"${pnl_details['pnl_usd_after_fees']:.2f}",
            f"{pnl_details['pnl_percentage_after_fees']:.2f}%",
        )

    def calculate_liquidation_price(self) -> None:
        """Calculate and emit Liquidation Price."""
        if self.associated_position is None:
            # Emit 0 or handle None in view? The view expects a value to format.
            # If I emit 0, it might show $0.0000.
            # I will emit Decimal(0) and let view handle it, or maybe None?
            # Signal is Decimal.
            self.update_liquidation.emit(Decimal(0))
            return

        liquidation_price = self.exchange.calculate_liquidation_price(self.associated_position)
        self.update_liquidation.emit(liquidation_price)

    def update_position_size(self, new_size: Decimal) -> None:
        """Update associated position size (local copy).

        Args:
            new_size (Decimal): New size.
        """
        if self.associated_position is not None:
            self.associated_position["position_size_stable"] = new_size

    def execute_order(self, trigger_price: Decimal, amount: Decimal, order_type_value: int) -> None:
        """Execute the order.

        Args:
            trigger_price (Decimal): Trigger price.
            amount (Decimal): Amount.
            order_type_value (int): Order type value.
        """
        order_type = PerpsTradeType(order_type_value)
        order = OrderData(
            id=self.order_data["id"],
            pair=self.order_data["pair"],
            trade_direction=self.order_data["trade_direction"],
            order_type=order_type,
            trigger_price=trigger_price,
            size_stable=amount,
            reduce_only=self.order_data["reduce_only"],
        )
        self.execute_order_signal.emit(order)
