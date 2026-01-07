"""Account Info Presenter."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

from qasync import asyncSlot

from plutus_terminal.ui.presenter.base import BasePresenter, BaseView

if TYPE_CHECKING:
    from decimal import Decimal
    from plutus_terminal.core.session import Session


class AccountInfoView(BaseView, Protocol):
    """Interface for the Account Info View."""

    @abstractmethod
    def set_balance(self, balance: str) -> None:
        """Set the balance text."""
        ...

    @abstractmethod
    def set_exchange_info(self, info: dict[str, str]) -> None:
        """Set the exchange info data."""
        ...

    @abstractmethod
    def set_approve_button_visible(self, visible: bool) -> None:
        """Set the visibility of the approve button."""
        ...


class AccountInfoPresenter(BasePresenter[AccountInfoView]):
    """Presenter for the Account Info widget."""

    def __init__(self, view: AccountInfoView, session: Session) -> None:
        """Initialize presenter."""
        super().__init__(view)
        self.session = session
        self._is_active = False

    def start(self) -> None:
        """Start listening to events."""
        self._is_active = True
        self.session.message_bus.balance_fetched.connect(self.on_balance_fetched)
        self.session.exchange_changed.connect(self.on_exchange_changed)

        # Initial load
        if self.session.current_exchange:
            self.on_exchange_changed()

    def stop(self) -> None:
        """Stop listening to events."""
        self._is_active = False
        self.session.message_bus.balance_fetched.disconnect(self.on_balance_fetched)
        self.session.exchange_changed.disconnect(self.on_exchange_changed)

    def on_balance_fetched(self, balance: Decimal) -> None:
        """Handle balance fetched event."""
        self.view.set_balance(f"${balance:.3f} USD")

    @asyncSlot()
    async def on_exchange_changed(self) -> None:
        """Handle exchange changed event."""
        exchange = self.session.current_exchange
        if not exchange:
            return

        # Update Info
        self.view.set_exchange_info(exchange.account_info)

        # Update Approve Button Visibility
        is_ready = await exchange.is_ready_to_trade()
        self.view.set_approve_button_visible(not is_ready)

    @asyncSlot()
    async def on_approve_clicked(self) -> None:
        """Handle approve button click."""
        exchange = self.session.current_exchange
        if not exchange:
            return

        await exchange.approve_for_trading()
        # Re-check visibility
        is_ready = await exchange.is_ready_to_trade()
        self.view.set_approve_button_visible(not is_ready)
