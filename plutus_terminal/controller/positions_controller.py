"""Controller for PositionsTable."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.types_ import PerpsPosition


class PositionsController(QObject):
    """Controller for PositionsTable."""

    refresh_table = Signal()
    update_pnl = Signal(dict) # Cached prices
    exchange_updated = Signal(object) # ExchangeBase

    def __init__(self, ui_controller: UIController) -> None:
        """Initialize controller.

        Args:
            ui_controller (UIController): UI Controller.
        """
        super().__init__()
        self.ui_controller = ui_controller
        self.exchange = ui_controller.current_exchange
        self.positions: list[PerpsPosition] = []

        self.connect_signals()

    def connect_signals(self) -> None:
        """Connect signals."""
        self.ui_controller.exchange_changed.connect(self.on_exchange_changed)
        self.ui_controller.message_bus.positions_fetched.connect(self.on_positions_fetched)
        self.ui_controller.message_bus.subscribed_prices_fetched.connect(self.on_prices_fetched)

    def on_positions_fetched(self, positions: list[PerpsPosition]) -> None:
        """Handle fetched positions.

        Args:
            positions (list[PerpsPosition]): Fetched positions.
        """
        self.positions = positions
        self.refresh_table.emit()

    def on_prices_fetched(self, prices: dict) -> None:
        """Handle fetched prices.

        Args:
            prices (dict): Fetched prices.
        """
        self.update_pnl.emit(prices)

    async def close_position(self, position: PerpsPosition) -> None:
        """Close position.

        Args:
            position (PerpsPosition): Position to close.
        """
        await self.exchange.close_position(position)

    async def create_reduce_order(self, **kwargs) -> None:
        """Create reduce order.

        Args:
            **kwargs: Arguments for reduce order.
        """
        await self.exchange.create_reduce_order(**kwargs)

    def calculate_collateral_delta(self, position: PerpsPosition, new_size: Decimal) -> Decimal:
        """Calculate collateral delta.

        Args:
            position (PerpsPosition): Position.
            new_size (Decimal): New size.

        Returns:
            Decimal: Collateral delta.
        """
        if position["position_size_stable"] == new_size:
            return Decimal(0)

        return (new_size * position["collateral_stable"]) / position["position_size_stable"]

    def calculate_pnl(self, position: PerpsPosition, current_price: Decimal) -> dict:
        """Calculate PnL.

        Args:
            position (PerpsPosition): Position.
            current_price (Decimal): Current price.

        Returns:
            dict: PnL details.
        """
        return self.exchange.calculate_pnl(position, current_price)

    @asyncSlot()
    async def on_exchange_changed(self) -> None:
        """Handle exchange change."""
        self.exchange = self.ui_controller.current_exchange
        self.exchange_updated.emit(self.exchange)
        self.positions = []
        self.refresh_table.emit()
