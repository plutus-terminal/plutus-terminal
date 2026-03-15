"""Controller for account-info widget orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING
import weakref

from PySide6.QtCore import QObject
from qasync import asyncSlot

from plutus_terminal.controller.widgets.ui_update_batcher import UiUpdateBatcher

if TYPE_CHECKING:
    from decimal import Decimal

    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.ui.widgets.account_info import AccountInfo


class AccountInfoController(QObject):
    """Coordinate account-info widget events and async actions."""

    def __init__(self, ui_controller: UIController, view: AccountInfo) -> None:
        """Initialize controller with explicit view dependencies."""
        super().__init__(parent=view)
        self._ui_controller = ui_controller
        self._view_ref: weakref.ReferenceType[AccountInfo] = weakref.ref(view)
        self._ui_batcher = UiUpdateBatcher.shared()
        self._connect_signals()

    def _view(self) -> AccountInfo | None:
        """Return the live view instance when available."""
        return self._view_ref()

    def _connect_signals(self) -> None:
        """Connect external and user-driven signals."""
        view = self._view()
        if view is None:
            return
        view.approve_btn.clicked.connect(self.handle_approve_for_trading)
        self._ui_controller.message_bus.balance_fetched.connect(self.refresh_for_balance)
        self._ui_controller.message_bus.positions_fetched.connect(self.schedule_market_data_refresh)
        self._ui_controller.exchange_changed.connect(self.handle_exchange_changed)

    def refresh_for_balance(self, _balance: Decimal) -> None:
        """Refresh the account snapshot after a balance event."""
        self.schedule_market_data_refresh()

    def refresh_account_snapshot(self, *_args: object) -> None:
        """Refresh account-info rows from current exchange state."""
        view = self._view()
        if view is None:
            return
        view.refresh_exchange_account_info()

    def schedule_market_data_refresh(self, *_args: object) -> None:
        """Batch account snapshot redraws triggered by market data."""
        view = self._view()
        if view is None:
            return
        self._ui_batcher.submit(
            f"account-info-refresh:{id(view)}",
            view.refresh_exchange_account_info,
        )

    @asyncSlot()
    async def set_approve_btn_visibility(self) -> None:
        """Update the approve button visibility from exchange readiness."""
        view = self._view()
        if view is None:
            return
        if await self._ui_controller.current_exchange.is_ready_to_trade():
            view.approve_btn.setVisible(False)
            return
        view.approve_btn.setVisible(True)

    @asyncSlot()
    async def handle_approve_for_trading(self) -> None:
        """Approve trading and refresh button visibility."""
        await self._ui_controller.current_exchange.approve_for_trading()
        await self.set_approve_btn_visibility()

    @asyncSlot()
    async def handle_exchange_changed(self) -> None:
        """Refresh the widget after an exchange change."""
        self.refresh_account_snapshot()
        await self.set_approve_btn_visibility()
