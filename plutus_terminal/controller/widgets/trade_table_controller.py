"""Controller for trade-table widget orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING
import weakref

from PySide6.QtCore import QObject

from plutus_terminal.controller.widgets.ui_update_batcher import UiUpdateBatcher

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
    from plutus_terminal.ui.widgets.trade_table import TradeTable


class TradeTableController(QObject):
    """Coordinate trade-table subscriptions and view refreshes."""

    def __init__(self, ui_controller: UIController, view: TradeTable) -> None:
        """Initialize controller with the owning widget."""
        super().__init__(parent=view)
        self._ui_controller = ui_controller
        self._view_ref: weakref.ReferenceType[TradeTable] = weakref.ref(view)
        self._ui_batcher = UiUpdateBatcher.shared()
        self._connect_signals()

    def _view(self) -> TradeTable | None:
        """Return the live view instance when available."""
        return self._view_ref()

    def _connect_signals(self) -> None:
        """Connect message-bus and widget events."""
        view = self._view()
        if view is None:
            return
        view.positions_table.row_clicked.connect(self._ui_controller.change_current_pair)
        self._ui_controller.message_bus.positions_fetched.connect(self.handle_positions_fetched)
        self._ui_controller.message_bus.orders_fetched.connect(self.handle_orders_fetched)
        self._ui_controller.message_bus.subscribed_prices_fetched.connect(
            self.handle_prices_fetched
        )
        self._ui_controller.message_bus.balance_fetched.connect(self.handle_balance_fetched)
        view.liquidation_refresh_timer.timeout.connect(view.refresh_liquidation_column)
        view.orders_refresh_timer.timeout.connect(view.flush_order_refresh)
        self._ui_controller.exchange_changed.connect(self.handle_exchange_changed)

    def handle_exchange_changed(self) -> None:
        """Refresh view state after exchange changes."""
        view = self._view()
        if view is None:
            return
        view.handle_new_exchange()

    def handle_positions_fetched(self, positions: list[PerpsPosition]) -> None:
        """Forward positions to the view."""
        view = self._view()
        if view is None:
            return
        view.update_positions(positions)

    def handle_orders_fetched(self, orders: list[OrderData]) -> None:
        """Coalesce orders via the view."""
        view = self._view()
        if view is None:
            return
        view.schedule_order_refresh(orders)

    def handle_prices_fetched(self, cached_prices: dict) -> None:
        """Forward market prices to the view."""
        view = self._view()
        if view is None:
            return
        self._ui_batcher.submit(
            f"trade-table-prices:{id(view)}",
            lambda: view.update_prices(cached_prices),
        )

    def handle_balance_fetched(self, _balance: object) -> None:
        """Trigger a coalesced liquidation refresh."""
        view = self._view()
        if view is None:
            return
        self._ui_batcher.submit(
            f"trade-table-liquidation:{id(view)}",
            view.schedule_liquidation_refresh,
        )
