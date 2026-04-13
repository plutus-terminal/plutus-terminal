"""Controller for perpetual-trade widget orchestration."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast
import weakref

from PySide6.QtCore import QObject
from qasync import asyncSlot

from plutus_terminal.controller.widgets.ui_update_batcher import UiUpdateBatcher
from plutus_terminal.core.exceptions import InvalidOrderSizeError
from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from PySide6 import QtWidgets

    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.ui.widgets.perps_trade import (
        LimitTradeWidget,
        MarketTradeWidget,
        PerpsTradeWidget,
        StopTradeWidget,
    )


class PerpsTradeController(QObject):
    """Coordinate widget signal wiring and external state reactions."""

    def __init__(self, ui_controller: UIController, view: PerpsTradeWidget) -> None:
        """Initialize controller with the owning widget."""
        super().__init__(parent=view)
        self._ui_controller = ui_controller
        self._view_ref: weakref.ReferenceType[PerpsTradeWidget] = weakref.ref(view)
        self._ui_batcher = UiUpdateBatcher.shared()
        self._connect_signals()

    def _view(self) -> PerpsTradeWidget | None:
        """Return the live view instance when available."""
        return self._view_ref()

    def _connect_signals(self) -> None:
        """Connect widget, app-config, and message-bus signals."""
        view = self._view()
        if view is None:
            return
        message_bus = self._ui_controller.message_bus
        app_config = self._ui_controller.app_config

        message_bus.subscribed_prices_fetched.connect(self.handle_market_data_fetched)
        message_bus.balance_fetched.connect(self.handle_balance_fetched)

        self._ui_controller.exchange_changed.connect(self.handle_exchange_changed)
        self._ui_controller.pair_changed.connect(self.handle_pair_changed)

        app_config.trade_value_high_changed.connect(view.update_trade_buttons)
        app_config.trade_value_low_changed.connect(view.update_trade_buttons)
        app_config.trade_value_medium_changed.connect(view.update_trade_buttons)
        app_config.trade_value_lowest_changed.connect(view.update_trade_buttons)
        app_config.leverage_changed.connect(self.sync_leverage_values)

        view.pair_combo_box.currentIndexChanged.connect(self.handle_pair_combo_index_changed)
        view.leverage_group.buttonClicked.connect(self.handle_leverage_button_clicked)

    def handle_balance_fetched(self, *_args: object) -> None:
        """Refresh liquidation previews after balance updates."""
        self.schedule_market_data_refresh()

    def handle_market_data_fetched(self, _cached_prices: dict) -> None:
        """Batch liquidation preview refreshes on market-data ticks."""
        self.schedule_market_data_refresh()

    def schedule_market_data_refresh(self) -> None:
        """Batch liquidation preview redraws for market-data-driven changes."""
        view = self._view()
        if view is None:
            return
        self._ui_batcher.submit(
            f"perps-trade-liquidation:{id(view)}",
            view.update_liquidation_info,
        )

    def handle_percent_button_click(self, button: QtWidgets.QAbstractButton) -> None:
        """Size the active trade entry from account balance percentage."""
        view = self._view()
        if view is None:
            return
        current_widget = view.current_trade_widget()
        if current_widget is None:
            return
        balance = view.exchange.stable_balance
        percentage = Decimal(current_widget.percent_group.id(button)) / Decimal(100)
        current_widget.amount_box.setValue(balance * percentage)

    def refresh_trade_summary(self) -> None:
        """Refresh fee, leverage, and liquidation summary labels."""
        view = self._view()
        if view is None:
            return
        current_widget = view.current_trade_widget()
        if current_widget is None:
            return
        amount = current_widget.amount_box.value()
        margin_fee = view.exchange.calculate_margin_fee(Decimal(amount) * view.leverage_value())
        view.set_fee_value(f"${margin_fee:.3f}")
        view.set_leverage_info_value(f"{view.leverage_value()}x")
        view.update_liquidation_info()

    @asyncSlot()
    async def handle_quick_trade_click(
        self,
        option_key: str,
        direction: PerpsTradeDirection,
    ) -> None:
        """Create a quick market order from configured preset values."""
        view = self._view()
        if view is None:
            return
        amount = getattr(self._ui_controller.app_config, option_key)
        pair = view.current_pair_data()
        try:
            await view.exchange.create_order(
                pair,
                amount,
                direction,
                PerpsTradeType.MARKET,
            )
        except InvalidOrderSizeError as error:
            Toast.show_message(f"{error}", type_=ToastType.ERROR)
        except Exception as error:  # noqa: BLE001
            Toast.show_message(f"Failed to create order: {error}", type_=ToastType.ERROR)

    def get_trade_type(self) -> PerpsTradeType:
        """Return the currently selected trade type."""
        view = self._view()
        if view is None:
            return PerpsTradeType.LIMIT
        if view.is_market_tab_active():
            return PerpsTradeType.MARKET
        if view.is_stop_tab_active():
            return PerpsTradeType.STOP_MARKET
        return PerpsTradeType.LIMIT

    @asyncSlot()
    async def create_order(self, direction: PerpsTradeDirection) -> None:
        """Create an order from the active trade-entry tab."""
        view = self._view()
        if view is None:
            return
        current_tab = view.current_trade_widget()
        if current_tab is None:
            return
        pair = view.current_pair_data()
        amount = Decimal(current_tab.get_amount())
        trade_type = self.get_trade_type()
        execution_price: Decimal | None = None
        stop_loss: float | None = 0.0
        take_profit: float | None = 0.0
        if view.is_limit_widget(current_tab):
            limit_tab = cast("LimitTradeWidget", current_tab)
            execution_price = Decimal(limit_tab.get_target_price())
            stop_loss = limit_tab.get_stop_loss()
            take_profit = limit_tab.get_take_profit()
        elif view.is_stop_widget(current_tab):
            stop_tab = cast("StopTradeWidget", current_tab)
            execution_price = Decimal(stop_tab.get_trigger_price())
        else:
            market_tab = cast("MarketTradeWidget", current_tab)
            stop_loss = market_tab.get_stop_loss()
            take_profit = market_tab.get_take_profit()
        try:
            await view.exchange.create_order(
                pair,
                amount,
                direction,
                trade_type,
                execution_price,
                take_profit,
                stop_loss,
            )
        except InvalidOrderSizeError as error:
            Toast.show_message(f"{error}", type_=ToastType.ERROR)

    @asyncSlot(int)
    async def handle_pair_combo_index_changed(self, index: int) -> None:
        """Change current pair from the combo-box selection."""
        view = self._view()
        if view is None:
            return
        pair = view.pair_combo_box.itemData(index)
        if not isinstance(pair, str):
            return
        await self._ui_controller.change_current_pair(pair)

    def sync_leverage_values(self) -> None:
        """Sync leverage controls from app-config state."""
        view = self._view()
        if view is None:
            return
        view.set_max_leverage(
            view.exchange.max_leverage_for_pair(self._ui_controller.current_pair),
        )
        view.set_leverage_spin_value(self._ui_controller.app_config.leverage)
        self.refresh_trade_summary()
        view.update_leverage_buttons(self._ui_controller.app_config.leverage)

    @asyncSlot()
    async def handle_leverage_button_clicked(self, button: QtWidgets.QRadioButton) -> None:
        """Mirror leverage button clicks into the spin control and exchange."""
        view = self._view()
        if view is None:
            return
        await self.set_leverage_spin(view.leverage_group.id(button))

    @asyncSlot()
    async def set_leverage_spin(self, leverage_value: int) -> None:
        """Sync leverage spin, summary labels, and exchange leverage."""
        view = self._view()
        if view is None:
            return
        view.set_leverage_spin_value(leverage_value)
        self.refresh_trade_summary()
        view.update_leverage_buttons(leverage_value)
        await self._set_leverage()

    @asyncSlot()
    async def _set_leverage(self) -> None:
        """Push the selected leverage to the current exchange."""
        view = self._view()
        if view is None:
            return
        leverage_value = view.leverage_value()
        pair = view.current_pair_data()
        coin = view.exchange.format_coin_from_pair(pair)
        await self._ui_controller.set_leverage(coin, leverage_value)
        if self._ui_controller.app_config.leverage != leverage_value:
            view.set_leverage_spin_value(self._ui_controller.app_config.leverage)
            view.update_leverage_buttons(self._ui_controller.app_config.leverage)

    @asyncSlot(str)
    async def handle_pair_changed(self, pair: str) -> None:
        """Refresh displayed pair state after pair changes."""
        view = self._view()
        if view is None:
            return
        simplified_pair = view.exchange.format_simple_pair_from_pair(pair)
        pair_max_leverage = view.exchange.max_leverage_for_pair(pair)
        requested_leverage = self._ui_controller.app_config.leverage
        view.set_pair_text(simplified_pair)
        view.set_max_leverage(pair_max_leverage)
        coin = view.exchange.format_coin_from_pair(pair)
        await self._ui_controller.set_leverage(coin, requested_leverage)
        if self._ui_controller.app_config.leverage != requested_leverage:
            view.set_leverage_spin_value(self._ui_controller.app_config.leverage)
            view.update_leverage_buttons(self._ui_controller.app_config.leverage)

    def handle_exchange_changed(self) -> None:
        """Refresh widget state after exchange changes."""
        view = self._view()
        if view is None:
            return
        view.set_exchange(self._ui_controller.current_exchange)
        view.populate_pairs_from_exchange()
        view.update_trade_buttons()
        current_pair = self._ui_controller.current_pair
        view.set_pair_text(view.exchange.format_simple_pair_from_pair(current_pair))
        view.set_max_leverage(view.exchange.max_leverage_for_pair(current_pair))
        view.set_leverage_spin_value(self._ui_controller.app_config.leverage)
        view.update_leverage_buttons(self._ui_controller.app_config.leverage)
        self.refresh_trade_summary()

    def handle_tab_changed(self) -> None:
        """Refresh derived fields after trade-tab changes."""
        view = self._view()
        if view is None:
            return
        self.refresh_trade_summary()
        view.update_trade_type_button_positions()

    def refresh_limit_price(self) -> None:
        """Fill the limit-price field from the latest cached price."""
        view = self._view()
        if view is None:
            return
        cached_pair = view.exchange.cached_prices.get(view.current_pair_data())
        if cached_pair is None or "price" not in cached_pair:
            return
        cached_price = cached_pair["price"]
        view.set_limit_price(cached_price)
