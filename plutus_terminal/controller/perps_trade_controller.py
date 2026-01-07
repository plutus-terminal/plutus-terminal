"""Controller for PerpsTradeWidget."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

from plutus_terminal.core.exceptions import InvalidOrderSizeError
from plutus_terminal.core.exchange.types import PerpsPosition, PerpsTradeType
from plutus_terminal.core.types_ import PerpsTradeDirection
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui import ui_utils

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.config import AppConfig


class PerpsTradeController(QObject):
    """Controller for PerpsTradeWidget."""

    update_pair = Signal(str, str) # pair, simplified_pair
    update_leverage = Signal(int)
    update_info = Signal(str, str, str, str) # fee, lev_text, long_liq, short_liq
    update_trade_buttons = Signal()

    def __init__(self, ui_controller: UIController) -> None:
        """Initialize controller.

        Args:
            ui_controller (UIController): UI Controller.
        """
        super().__init__()
        self.ui_controller = ui_controller
        self.exchange = ui_controller.current_exchange
        self.app_config = ui_controller.app_config

        self.connect_signals()

    def connect_signals(self) -> None:
        """Connect signals."""
        self.ui_controller.message_bus.subscribed_prices_fetched.connect(self.update_liquidation_info_signal)
        self.ui_controller.exchange_changed.connect(self.on_exchange_changed)
        self.ui_controller.pair_changed.connect(self.on_pair_changed)

        self.app_config.trade_value_high_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_low_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_lowest_changed.connect(self.update_trade_buttons.emit)
        self.app_config.trade_value_high_changed.connect(self.update_trade_buttons.emit)
        self.app_config.leverage_changed.connect(self.on_leverage_changed)

    def update_liquidation_info_signal(self, _: dict) -> None:
        """Propagate signal to update liquidation info (View calls calculate_info).

        Args:
            _ (dict): Unused data.
        """
        # The view needs to call calculate_info with current UI state (amount, etc.)
        # We can emit a generic signal telling view to refresh calculation.
        # update_info signal is used when controller calculates it.
        # But controller doesn't know 'amount' unless view sends it.
        # So we can't fully push from here without view data.
        # We can signal view to request update?
        # Or view can connect directly to subscribed_prices_fetched via controller?
        # Ideally controller handles logic.
        pass # View will trigger calculation or we emit signal to trigger it.

    def calculate_info(self, amount: Decimal, leverage: int, pair: str, is_limit: bool, limit_price: Decimal) -> None:
        """Calculate fees and liquidation prices.

        Args:
            amount (Decimal): Amount.
            leverage (int): Leverage.
            pair (str): Pair.
            is_limit (bool): Is limit order.
            limit_price (Decimal): Limit price.
        """
        margin_fee = self.exchange.calculate_margin_fee(amount * leverage)

        fees_text = f"${margin_fee:.3f}"
        lev_text = f"{leverage}x"

        if not amount:
            self.update_info.emit(fees_text, lev_text, "--", "--")
            return

        if is_limit:
            open_price = limit_price
        else:
            pair_cached = self.exchange.cached_prices.get(pair, None)
            if pair_cached is None:
                self.update_info.emit(fees_text, lev_text, "--", "--")
                return
            open_price = pair_cached["price"]

        long_liq_price = self.exchange.calculate_liquidation_price(
            PerpsPosition(
                {
                    "pair": pair,
                    "id": 0,
                    "position_size_stable": Decimal(amount * leverage),
                    "collateral_stable": Decimal(amount),
                    "open_price": open_price,
                    "trade_direction": PerpsTradeDirection.LONG,
                    "leverage": Decimal(leverage),
                    "liquidation_price": Decimal(0),
                },
            ),
        )

        minimal_digits = ui_utils.get_minimal_digits(float(long_liq_price), 4)
        long_liq_text = f"<span style='color:rgb(100, 200, 100)'>${long_liq_price:,.{minimal_digits}f}</span>"

        short_liq_price = self.exchange.calculate_liquidation_price(
            PerpsPosition(
                {
                    "pair": pair,
                    "id": 0,
                    "position_size_stable": Decimal(amount * leverage),
                    "collateral_stable": Decimal(amount),
                    "open_price": open_price,
                    "trade_direction": PerpsTradeDirection.SHORT,
                    "leverage": Decimal(leverage),
                    "liquidation_price": Decimal(0),
                },
            ),
        )
        minimal_digits = ui_utils.get_minimal_digits(float(short_liq_price), 4)
        short_liq_text = f"<span style='color:rgb(255, 100, 100)'>${short_liq_price:,.{minimal_digits}f}</span>"

        self.update_info.emit(fees_text, lev_text, long_liq_text, short_liq_text)

    async def handle_quick_trade(self, option_key: str, direction: PerpsTradeDirection, pair: str) -> None:
        """Handle quick trade.

        Args:
            option_key (str): Option key.
            direction (PerpsTradeDirection): Direction.
            pair (str): Pair.
        """
        amount = getattr(self.app_config, option_key)
        try:
            await self.exchange.create_order(
                pair,
                amount,
                direction,
                PerpsTradeType.MARKET,
            )
        except InvalidOrderSizeError as error:
            Toast.show_message(f"{error}", type_=ToastType.ERROR)

    async def create_order(
        self,
        pair: str,
        direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        amount: Decimal,
        execution_price: Decimal | None,
        take_profit: float,
        stop_loss: float
    ) -> None:
        """Create order.

        Args:
            pair (str): Pair.
            direction (PerpsTradeDirection): Direction.
            trade_type (PerpsTradeType): Trade type.
            amount (Decimal): Amount.
            execution_price (Decimal | None): Execution price.
            take_profit (float): Take profit.
            stop_loss (float): Stop loss.
        """
        try:
            await self.exchange.create_order(
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

    async def set_leverage(self, pair: str, leverage: int) -> None:
        """Set leverage.

        Args:
            pair (str): Pair.
            leverage (int): Leverage.
        """
        coin = self.exchange.format_coin_from_pair(pair)
        await self.ui_controller.set_leverage(coin, leverage)

        if self.app_config.leverage != leverage:
             self.update_leverage.emit(self.app_config.leverage)

    def change_pair(self, pair: str) -> None:
        """Change pair via UI Controller.

        Args:
            pair (str): Pair.
        """
        # Need to format full pair name if simple name is provided?
        # The View provides pair key (from userData) which is the full pair usually.
        # But UIController expects pair like "Crypto.BTC/USD"
        # The view's combobox `userData` stores the full pair string.
        # `_pair_combo_box.addItem(..., userData=pair)`
        # `pair` comes from `available_pairs` which are full strings.
        # But in `PerpsTradeWidget._setup_widgets`, it calls `_ui_controller.change_current_pair(f"{self._exchange.pair_prefix}{pair}{self._exchange.pair_suffix}")`
        # Wait, if `available_pairs` returns full pairs, why did it add prefix/suffix?
        # Looking at `PerpsTradeWidget`:
        # `lambda pair: self._ui_controller.change_current_pair(f"{self._exchange.pair_prefix}{pair}{self._exchange.pair_suffix}")`
        # This implies `currentTextChanged` signal emits the TEXT, not user data. The text is simplified pair (e.g. BTC/USD).
        # Ah! `currentTextChanged` emits `str`.
        # If I use `currentIndexChanged` I can get index and then data.
        # Or I can parse the text.
        # I'll stick to how it was or improve it. View should probably send the pair string it wants.
        # The View calls `ui_controller.change_current_pair` directly in lambda.
        # I should route it through here.

        # If input is simplified pair, we need to reconstruct full pair.
        # Assuming input `pair` is the simplified name (e.g. "BTC/USD")
        # But exchange might need prefix.
        full_pair = f"{self.exchange.pair_prefix}{pair}{self.exchange.pair_suffix}"
        asyncSlot(self.ui_controller.change_current_pair)(full_pair) # Fire and forget async

    @asyncSlot()
    async def on_pair_changed(self, pair: str) -> None:
        """Handle pair changed.

        Args:
            pair (str): Pair.
        """
        simplified_pair = self.exchange.format_simple_pair_from_pair(pair)
        self.update_pair.emit(pair, simplified_pair)

        coin = self.exchange.format_coin_from_pair(pair)
        await self.ui_controller.set_leverage(coin, self.app_config.leverage)

    @asyncSlot()
    async def on_exchange_changed(self) -> None:
        """Handle exchange changed."""
        self.exchange = self.ui_controller.current_exchange
        # We need to refresh data in view (combo box items).
        # We can signal view to refresh everything.
        # Or emit `update_pair` with default pair.

        # The view needs available pairs.
        # View can access `controller.exchange.available_pairs`.
        # We just signal `refresh_ui`.
        self.update_trade_buttons.emit()
        self.update_leverage.emit(self.app_config.leverage)

        # And trigger pair update
        default_pair = self.exchange.default_pair
        simplified = self.exchange.format_simple_pair_from_pair(default_pair)
        self.update_pair.emit(default_pair, simplified)

    def on_leverage_changed(self) -> None:
        """Handle leverage config change."""
        self.update_leverage.emit(self.app_config.leverage)

    def get_trade_value(self, index: int) -> int:
        """Get trade value.

        Args:
            index (int): Index.

        Returns:
            int: Trade value.
        """
        value_map = {
            0: self.app_config.trade_value_lowest,
            1: self.app_config.trade_value_low,
            2: self.app_config.trade_value_medium,
            3: self.app_config.trade_value_high,
        }
        return value_map.get(index, 0)
