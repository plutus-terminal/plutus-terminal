"""Widget for Trading Perpetuals."""

from __future__ import annotations

from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Signal
from qasync import asyncSlot

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import InvalidOrderSizeError
from plutus_terminal.core.exchange.types import PerpsPosition
from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType
from plutus_terminal.ui import ui_utils
from plutus_terminal.ui.widgets.decimal_spin_box import DecimalSpinBoxWithButton
from plutus_terminal.ui.widgets.double_spin_button import DoubleSpinBoxWithButton
from plutus_terminal.ui.widgets.toast import Toast, ToastType
from plutus_terminal.ui.widgets.top_bar_widget import TopBar

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.base import ExchangeBase


class PerpsTradeWidget(QtWidgets.QWidget):
    """Widget for Trading Perpetuals."""

    pair_changed = Signal(str)

    def __init__(
        self,
        exchange: ExchangeBase,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)
        self._exchange = exchange

        self.main_layout = QtWidgets.QGridLayout(self)
        self.top_bar = TopBar("Perps Trade")

        self._quick_buy_grp = QtWidgets.QGroupBox("Quick Market Buy")
        self._quick_buy_layout = QtWidgets.QGridLayout()
        self._long_lowest_btn = QtWidgets.QPushButton()
        self._long_low_btn = QtWidgets.QPushButton()
        self._long_medium_btn = QtWidgets.QPushButton()
        self._long_high_btn = QtWidgets.QPushButton()
        self._long_btns = [
            self._long_lowest_btn,
            self._long_low_btn,
            self._long_medium_btn,
            self._long_high_btn,
        ]
        self._short_lowest_btn = QtWidgets.QPushButton()
        self._short_low_btn = QtWidgets.QPushButton()
        self._short_medium_btn = QtWidgets.QPushButton()
        self._short_high_btn = QtWidgets.QPushButton()
        self._short_btns = [
            self._short_lowest_btn,
            self._short_low_btn,
            self._short_medium_btn,
            self._short_high_btn,
        ]

        self._pair_grp = QtWidgets.QGroupBox("Current Pair")
        self._pair_combo_box = QtWidgets.QComboBox()

        self._leverage_box = QtWidgets.QGroupBox("Current Pair Leverage")
        self._leverage_box_layout = QtWidgets.QGridLayout()
        self._leverage_label = QtWidgets.QLabel("Leverage:")
        self._leverage_spin = QtWidgets.QSpinBox()
        self._leverage_group = QtWidgets.QButtonGroup()
        self._leverage_btn_layout = QtWidgets.QHBoxLayout()

        self._trade_tab = QtWidgets.QTabWidget()
        self._trade_type_market = MarketTradeWidget(
            quote_symbol=self._exchange.quote_symbol,
        )
        self._trade_type_market_layout = QtWidgets.QGridLayout()
        self._trade_type_limit = LimitTradeWidget(
            quote_symbol=self._exchange.quote_symbol,
        )
        self._trade_type_limit_layout = QtWidgets.QGridLayout()

        self._info_frame = QtWidgets.QFrame()
        self._info_layout = QtWidgets.QGridLayout()
        self._leverage_info_label = QtWidgets.QLabel("Leverage:")
        self._leverage_info_value = QtWidgets.QLabel("--")
        self._fees_label = QtWidgets.QLabel("Fees:")
        self._fees_value = QtWidgets.QLabel("--")
        self._liq_price_long_label = QtWidgets.QLabel("Est. Liq. Price LONG:")
        self._liq_price_long_value = QtWidgets.QLabel("--")
        self._liq_price_short_label = QtWidgets.QLabel("Est. Liq. Price SHORT:")
        self._liq_price_short_value = QtWidgets.QLabel("--")

        self._long_button = QtWidgets.QPushButton("Open Long")
        self._short_button = QtWidgets.QPushButton("Open Short")

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:  # noqa: PLR0915
        """Configure widgets."""
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar.icon.setPixmap(
            QtGui.QPixmap(":/icons/dollar_icon"),
        )

        option_keys = (
            "trade_value_lowest",
            "trade_value_low",
            "trade_value_medium",
            "trade_value_high",
        )

        self.update_trade_buttons()
        for index, btn in enumerate(self._long_btns):
            btn.setProperty("class", "LONG")
            btn.setMinimumHeight(25)
            btn.clicked.connect(
                partial(
                    self._handle_quick_trade_click,
                    option_keys[index],
                    PerpsTradeDirection.LONG,
                ),
            )
        for index, btn in enumerate(self._short_btns):
            btn.setProperty("class", "SHORT")
            btn.setMinimumHeight(25)
            btn.clicked.connect(
                partial(
                    self._handle_quick_trade_click,
                    option_keys[index],
                    PerpsTradeDirection.SHORT,
                ),
            )

        self._set_data_from_exchange()
        self._pair_combo_box.currentTextChanged.connect(
            lambda pair: self.pair_changed.emit(
                f"{self._exchange.pair_prefix}{pair}{self._exchange.pair_suffix}",
            ),
        )

        pair_layout = QtWidgets.QVBoxLayout()
        pair_layout.addWidget(self._pair_combo_box)
        self._pair_grp.setLayout(pair_layout)

        for value in (2, 5, 10, 20, 25, 50):
            button = QtWidgets.QRadioButton(str(value))
            self._leverage_group.addButton(button)
            self._leverage_group.setId(button, value)
            self._leverage_btn_layout.addWidget(button)
        self._leverage_group.buttonClicked.connect(self._set_leverage_button)

        self._leverage_spin.setMinimum(1)
        self._leverage_spin.setMaximum(50)
        self._leverage_spin.setValue(CONFIG.leverage)
        self._leverage_spin.editingFinished.connect(
            lambda: self._set_leverage_spin(
                self._leverage_spin.value(),
            ),
        )
        self._update_leverage_buttons(self._leverage_spin.value())

        self._trade_tab.setObjectName("tradeType")
        self._trade_tab.tabBar().setObjectName("tradeTypeTab")
        self._trade_tab.addTab(self._trade_type_market, "Market")
        self._trade_tab.addTab(self._trade_type_limit, "Limit")
        self._trade_tab.currentChanged.connect(self._update_tab)
        self._trade_tab.setMinimumHeight(self._trade_tab.sizeHint().height() + 5)
        self._trade_tab.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )

        self._trade_type_market.amount_changed.connect(
            self._update_info,
        )
        self._trade_type_market.percent_button_clicked.connect(
            self._handle_percent_button_click,
        )
        self._trade_type_limit.price_refresh_btn.clicked.connect(
            self._refresh_limit_price,
        )
        self._trade_type_limit.target_price_box.buttonClicked.connect(
            self._refresh_limit_price,
        )
        self._trade_type_limit.amount_changed.connect(
            self._update_info,
        )
        self._trade_type_limit.percent_button_clicked.connect(
            self._handle_percent_button_click,
        )

        self._info_frame.setObjectName("newsFrameQuote")
        self._leverage_info_value.setText(f"{self._leverage_spin.value()}x")
        self._leverage_info_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._fees_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._liq_price_long_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._liq_price_short_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self._long_button.setProperty("class", "LONG")
        self._long_button.setMinimumHeight(40)
        self._long_button.clicked.connect(
            partial(self._create_order, PerpsTradeDirection.LONG),
        )
        self._short_button.setProperty("class", "SHORT")
        self._short_button.setMinimumHeight(40)
        self._short_button.clicked.connect(
            partial(self._create_order, PerpsTradeDirection.SHORT),
        )

    def _setup_layout(self) -> None:
        """Configure layouts."""
        self.main_layout.addWidget(self.top_bar, 0, 0, 1, 2)

        self._quick_buy_layout.addWidget(self._long_lowest_btn, 0, 0)
        self._quick_buy_layout.addWidget(self._long_low_btn, 0, 1)
        self._quick_buy_layout.addWidget(self._long_medium_btn, 1, 0)
        self._quick_buy_layout.addWidget(self._long_high_btn, 1, 1)
        self._quick_buy_layout.addWidget(self._short_lowest_btn, 0, 2)
        self._quick_buy_layout.addWidget(self._short_low_btn, 0, 3)
        self._quick_buy_layout.addWidget(self._short_medium_btn, 1, 2)
        self._quick_buy_layout.addWidget(self._short_high_btn, 1, 3)
        self._quick_buy_grp.setLayout(self._quick_buy_layout)

        self.main_layout.addWidget(self._pair_grp, 1, 0, 1, 2)
        self.main_layout.addWidget(self._quick_buy_grp, 2, 0, 1, 2)

        self._leverage_box_layout.addWidget(self._leverage_label, 0, 0)
        self._leverage_box_layout.addWidget(self._leverage_spin, 0, 1)
        self._leverage_box_layout.addLayout(self._leverage_btn_layout, 1, 0, 1, 2)
        self._leverage_box.setLayout(self._leverage_box_layout)
        self.main_layout.addWidget(self._leverage_box, 3, 0, 1, 2)

        self.main_layout.addWidget(self._trade_tab, 4, 0, 1, 2)

        self._info_layout.addWidget(self._leverage_info_label, 0, 0)
        self._info_layout.addWidget(self._leverage_info_value, 0, 1)
        self._info_layout.addWidget(self._fees_label, 1, 0)
        self._info_layout.addWidget(self._fees_value, 1, 1)
        self._info_layout.addWidget(self._liq_price_long_label, 2, 0)
        self._info_layout.addWidget(self._liq_price_long_value, 2, 1)
        self._info_layout.addWidget(self._liq_price_short_label, 3, 0)
        self._info_layout.addWidget(self._liq_price_short_value, 3, 1)
        self._info_frame.setLayout(self._info_layout)
        self.main_layout.addWidget(self._info_frame, 5, 0, 1, 2)

        self.main_layout.addWidget(
            self._long_button,
            6,
            0,
            alignment=QtCore.Qt.AlignmentFlag.AlignBottom,
        )
        self.main_layout.addWidget(
            self._short_button,
            6,
            1,
            alignment=QtCore.Qt.AlignmentFlag.AlignBottom,
        )

    def _set_data_from_exchange(self) -> None:
        """Set data from exchange."""
        # Fill combo box with available pairs
        self._pair_combo_box.clear()
        for pair in sorted(self._exchange.available_pairs):
            self._pair_combo_box.addItem(
                self._exchange.format_simple_pair_from_pair(pair),
                userData=pair,
            )
        # Set current Text to be the default pair from exchange
        default_pair = self._exchange.default_pair
        default_pair = self._exchange.format_simple_pair_from_pair(default_pair)
        self._pair_combo_box.setCurrentText(default_pair)

        self.top_bar.title.setText(f"Persp Trade | {default_pair}")

    @asyncSlot()
    async def _set_leverage_spin(self, leverage_value: int) -> None:
        """Set leverage when spin is changed.

        Update buttons if values matches.

        Args:
            leverage_value (int): Leverage value.
        """
        self._leverage_spin.blockSignals(True)
        self._leverage_spin.setValue(leverage_value)
        self._leverage_spin.blockSignals(False)

        self._update_info()
        self._update_leverage_buttons(leverage_value)

        await self._set_leverage()

    def _update_leverage_buttons(self, leverage_value: int) -> None:
        """Update leverage buttons state based on leverage value."""
        if leverage_value in {2, 5, 10, 20, 25, 50}:
            self._leverage_group.button(int(leverage_value)).setChecked(True)
        else:
            button = self._leverage_group.checkedButton()
            if button:
                self._leverage_group.setExclusive(False)
                button.setChecked(False)
                self._leverage_group.setExclusive(True)

    @asyncSlot()
    async def _set_leverage_button(self, button: QtWidgets.QRadioButton) -> None:
        """Set leverage spin when button is clicked.

        Args:
            button (QtWidgets.QRadioButton): Leverage button clicked.
        """
        await self._set_leverage_spin(self._leverage_group.id(button))

    @asyncSlot()
    async def _set_leverage(self) -> None:
        """Set leverage on exchange for current pair.

        Args:
            leverage_value (int): Leverage value to set.
        """
        leverage_value = self._leverage_spin.value()
        pair = self._pair_combo_box.currentData()
        coin = self._exchange.format_coin_from_pair(pair)
        await self._exchange.set_leverage(coin, leverage_value)

        # In case the levarage was changed due to limits, ensure UI is up to date
        if CONFIG.leverage != leverage_value:
            self._leverage_spin.blockSignals(True)
            self._leverage_spin.setValue(CONFIG.leverage)
            self._update_leverage_buttons(CONFIG.leverage)
            self._leverage_spin.blockSignals(False)

    def _update_info(self) -> None:
        """Update frame info."""
        current_widget = self._trade_tab.currentWidget()
        if not isinstance(current_widget, MarketTradeWidget | LimitTradeWidget):
            return
        amount = current_widget.amount_box.value()
        margin_fee = self._exchange.calculate_margin_fee(
            Decimal(amount) * self._leverage_spin.value(),
        )
        self._fees_value.setText(f"${margin_fee:.3f}")

        leverage_value = self._leverage_spin.value()
        self._leverage_info_value.setText(f"{leverage_value}x")
        self.update_liquidation_info()

    def update_liquidation_info(self) -> None:
        """Update liquidation info."""
        current_widget = self._trade_tab.currentWidget()
        if not isinstance(current_widget, MarketTradeWidget | LimitTradeWidget):
            return

        amount = current_widget.amount_box.value()
        if not amount:
            self._liq_price_long_value.setText("--")
            self._liq_price_short_value.setText("--")
            return

        leverage_value = self._leverage_spin.value()
        pair = self._pair_combo_box.currentData()
        if isinstance(current_widget, LimitTradeWidget):
            open_price = Decimal(current_widget.target_price_box.value())
        else:
            pair_cached = self._exchange.cached_prices.get(pair, None)
            if pair_cached is None:
                return
            open_price = pair_cached["price"]

        long_liq_price = self._exchange.calculate_liquidation_price(
            PerpsPosition(
                {
                    "pair": pair,
                    "id": 0,
                    "position_size_stable": Decimal(amount * leverage_value),
                    "collateral_stable": Decimal(amount),
                    "open_price": open_price,
                    "trade_direction": PerpsTradeDirection.LONG,
                    "leverage": Decimal(leverage_value),
                    "liquidation_price": Decimal(0),
                },
            ),
        )

        minimal_digits = ui_utils.get_minimal_digits(float(long_liq_price), 4)
        self._liq_price_long_value.setText(
            f"<span style='color:rgb(100, 200, 100)'>${long_liq_price:,.{minimal_digits}f}</span>",
        )

        short_liq_price = self._exchange.calculate_liquidation_price(
            PerpsPosition(
                {
                    "pair": pair,
                    "id": 0,
                    "position_size_stable": Decimal(amount * leverage_value),
                    "collateral_stable": Decimal(amount),
                    "open_price": open_price,
                    "trade_direction": PerpsTradeDirection.SHORT,
                    "leverage": Decimal(leverage_value),
                    "liquidation_price": Decimal(0),
                },
            ),
        )
        minimal_digits = ui_utils.get_minimal_digits(float(short_liq_price), 4)
        self._liq_price_short_value.setText(
            f"<span style='color:rgb(255, 100, 100)'>${short_liq_price:,.{minimal_digits}f}</span>",
        )

    @asyncSlot()
    async def _handle_quick_trade_click(
        self,
        option_key: str,
        direction: PerpsTradeDirection,
    ) -> None:
        """Handle quick trade click."""
        amount = getattr(CONFIG, option_key)
        pair = self._pair_combo_box.currentData()
        try:
            await self._exchange.create_order(
                pair,
                amount,
                direction,
                PerpsTradeType.MARKET,
            )
        except InvalidOrderSizeError as error:
            Toast.show_message(
                f"{error}",
                type_=ToastType.ERROR,
            )

    def _handle_percent_button_click(self, button: QtWidgets.QAbstractButton) -> None:
        """Handle percent button click.

        Args:
            button (QtWidgets.QAbstractButton): Percent button clicked.
        """
        current_widget = self._trade_tab.currentWidget()
        if not isinstance(current_widget, MarketTradeWidget | LimitTradeWidget):
            return
        balance = self._exchange.stable_balance
        percentage = Decimal(current_widget.percent_group.id(button) / 100)
        current_widget.amount_box.setValue(balance * percentage)

    @asyncSlot()
    async def _create_order(
        self,
        direction: PerpsTradeDirection,
    ) -> None:
        """Create new order."""
        pair = self._pair_combo_box.currentData()
        current_tab = self._trade_tab.currentWidget()
        if not isinstance(current_tab, LimitTradeWidget) and not isinstance(
            current_tab,
            MarketTradeWidget,
        ):
            return
        amount = Decimal(current_tab.get_amount())
        trade_type = self.get_trade_type()
        # Get None in case the order is Market
        execution_price = (
            Decimal(current_tab.get_target_price())
            if isinstance(current_tab, LimitTradeWidget)
            else None
        )
        stop_loss = Decimal(current_tab.get_stop_loss())
        take_profit = Decimal(current_tab.get_take_profit())
        try:
            await self._exchange.create_order(
                pair,
                amount,
                direction,
                trade_type,
                execution_price,
                take_profit,
                stop_loss,
            )
        except InvalidOrderSizeError as error:
            Toast.show_message(
                f"{error}",
                type_=ToastType.ERROR,
            )

    def get_trade_type(self) -> PerpsTradeType:
        """Get trade type from active tab."""
        current_tab = self._trade_tab.currentWidget()
        if current_tab == self._trade_type_market:
            return PerpsTradeType.MARKET
        return PerpsTradeType.LIMIT

    @asyncSlot()
    async def update_current_pair(self, pair: str) -> None:
        """Update current pair.

        Args:
            pair (str): New pair.
        """
        simplified_pair = self._exchange.format_simple_pair_from_pair(pair)
        self._pair_combo_box.blockSignals(True)
        self._pair_combo_box.setCurrentText(simplified_pair)
        self._pair_combo_box.blockSignals(False)

        # Ensure leverage is set correctly
        coin = self._exchange.format_coin_from_pair(pair)
        await self._exchange.set_leverage(coin, CONFIG.leverage)

        self.top_bar.title.setText(f"Persp Trade | {simplified_pair}")

    def update_trade_buttons(self) -> None:
        """Update trade buttons values."""
        value_map = {
            0: CONFIG.trade_value_lowest,
            1: CONFIG.trade_value_low,
            2: CONFIG.trade_value_medium,
            3: CONFIG.trade_value_high,
        }
        for index, btn in enumerate(self._long_btns):
            btn.setText(f"${value_map[index]}")
        for index, btn in enumerate(self._short_btns):
            btn.setText(f"-${value_map[index]}")

    def _update_tab(self) -> None:
        """Update tab buttons."""
        self._update_info()
        self._trade_type_market.update_button_position()
        self._trade_type_limit.update_button_position()

    def _refresh_limit_price(self) -> None:
        """Refresh limit price."""
        self._trade_type_limit.target_price_box.setValue(
            self._exchange.cached_prices[self._pair_combo_box.currentData()]["price"],
        )

    def on_new_exchange(self, new_exchange: ExchangeBase) -> None:
        """Update info based on new exchange.

        Args:
            new_exchange (ExchangeBase): New exchangeBase.
        """
        self._exchange = new_exchange
        self._set_data_from_exchange()

    def on_new_account(self) -> None:
        """Update info based on new account."""
        self.blockSignals(True)
        self._leverage_spin.setValue(CONFIG.leverage)
        self._update_leverage_buttons(CONFIG.leverage)
        self.blockSignals(False)


class MarketTradeWidget(QtWidgets.QWidget):
    """Widget to fill a market trade."""

    amount_changed = Signal()
    percent_button_clicked = Signal(QtWidgets.QAbstractButton)

    def __init__(
        self,
        quote_symbol: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        self.amount_label = QtWidgets.QLabel("Amount:")
        self.amount_label.setFixedWidth(70)
        self.amount_box = DecimalSpinBoxWithButton(
            button_text=quote_symbol,
        )
        self.amount_box.decimalValueChanged.connect(lambda _: self.amount_changed.emit())
        self.percent_group = QtWidgets.QButtonGroup(self)
        self.percent_group_layout = QtWidgets.QHBoxLayout()
        for value in ("25%", "50%", "75%", "100%"):
            button = QtWidgets.QRadioButton(value)
            self.percent_group.addButton(button)
            self.percent_group.setId(button, int(value[:-1]))
            self.percent_group.buttonClicked.connect(self.percent_button_clicked)
            self.percent_group_layout.addWidget(button)

        amount_layout = QtWidgets.QHBoxLayout()
        amount_layout.addWidget(self.amount_label)
        amount_layout.addWidget(self.amount_box)

        self._take_profit_label = QtWidgets.QLabel("Take Profit:")
        self._take_profit_label.setFixedWidth(70)
        self.take_profit_box = DoubleSpinBoxWithButton(
            button_text="%",
        )
        self.take_profit_box.setDecimals(2)
        take_profit_layout = QtWidgets.QHBoxLayout()
        take_profit_layout.addWidget(self._take_profit_label)
        take_profit_layout.addWidget(self.take_profit_box)

        self._stop_loss_label = QtWidgets.QLabel("Stop Loss:")
        self._stop_loss_label.setFixedWidth(70)
        self.stop_loss_box = DoubleSpinBoxWithButton(
            button_text="%",
        )
        self.stop_loss_box.setDecimals(2)
        stop_loss_layout = QtWidgets.QHBoxLayout()
        stop_loss_layout.addWidget(self._stop_loss_label)
        stop_loss_layout.addWidget(self.stop_loss_box)

        self.main_layout.addLayout(amount_layout)
        self.main_layout.addLayout(self.percent_group_layout)
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        separator.setObjectName("divisor")
        self.main_layout.addWidget(separator)
        self.main_layout.addLayout(take_profit_layout)
        self.main_layout.addLayout(stop_loss_layout)
        self.main_layout.addStretch()

    def update_button_position(self) -> None:
        """Update button position."""
        self.amount_box.update_button_position()
        self.take_profit_box.update_button_position()
        self.stop_loss_box.update_button_position()

    def get_amount(self) -> Decimal:
        """Get amount."""
        return self.amount_box.value()

    def get_take_profit(self) -> float:
        """Get take profit."""
        return self.take_profit_box.value()

    def get_stop_loss(self) -> float:
        """Get stop loss."""
        return self.stop_loss_box.value()


class LimitTradeWidget(QtWidgets.QWidget):
    """Widget to fill a limit trade."""

    amount_changed = Signal()
    percent_button_clicked = Signal(QtWidgets.QAbstractButton)

    def __init__(
        self,
        quote_symbol: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent=parent)

        self.main_layout = QtWidgets.QGridLayout()
        self.setLayout(self.main_layout)

        self.amount_label = QtWidgets.QLabel("Amount:")
        self.amount_label.setFixedWidth(70)
        self.amount_box = DecimalSpinBoxWithButton(
            button_text=quote_symbol,
        )
        self.amount_box.decimalValueChanged.connect(lambda _: self.amount_changed.emit())
        self.percent_group = QtWidgets.QButtonGroup(self)
        self.percent_group_layout = QtWidgets.QHBoxLayout()
        for value in ("25%", "50%", "75%", "100%"):
            button = QtWidgets.QRadioButton(value)
            self.percent_group.addButton(button)
            self.percent_group.setId(button, int(value[:-1]))
            self.percent_group.buttonClicked.connect(self.percent_button_clicked)
            self.percent_group_layout.addWidget(button)

        self.target_price_label = QtWidgets.QLabel("Price:")
        self.target_price_label.setFixedWidth(70)

        self.target_price_box = DecimalSpinBoxWithButton(
            button_text=quote_symbol,
        )
        self.price_refresh_btn = QtWidgets.QPushButton()
        self.price_refresh_btn.setProperty("class", "borderless")
        self.price_refresh_btn.setIcon(
            QtGui.QIcon(":/icons/focus_icon"),
        )
        self.price_refresh_btn.setFixedWidth(25)

        self._take_profit_label = QtWidgets.QLabel("Take Profit:")
        self._take_profit_label.setFixedWidth(70)
        self.take_profit_box = DoubleSpinBoxWithButton(
            button_text="%",
        )
        self.take_profit_box.setDecimals(2)
        self.take_profit_box.setEnabled(False)

        self._stop_loss_label = QtWidgets.QLabel("Stop Loss:")
        self._stop_loss_label.setFixedWidth(70)
        self.stop_loss_box = DoubleSpinBoxWithButton(
            button_text="%",
        )
        self.stop_loss_box.setDecimals(2)
        self.stop_loss_box.setEnabled(False)

        self.main_layout.addWidget(self.amount_label, 0, 0)
        self.main_layout.addWidget(self.amount_box, 0, 1, 1, 2)
        self.main_layout.addLayout(self.percent_group_layout, 1, 0, 1, 3)
        self.main_layout.addWidget(self.target_price_label, 2, 0)
        self.main_layout.addWidget(self.target_price_box, 2, 1)
        self.main_layout.addWidget(self.price_refresh_btn, 2, 2)
        self.main_layout.setRowStretch(3, 1)
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        separator.setObjectName("divisor")
        self.main_layout.addWidget(separator, 3, 0, 1, 3)
        self.main_layout.addWidget(self._take_profit_label, 4, 0)
        self.main_layout.addWidget(self.take_profit_box, 4, 1, 1, 2)
        self.main_layout.addWidget(self._stop_loss_label, 5, 0)
        self.main_layout.addWidget(self.stop_loss_box, 5, 1, 1, 2)
        self.main_layout.rowStretch(6)

    def update_button_position(self) -> None:
        """Update button position."""
        self.amount_box.update_button_position()
        self.target_price_box.update_button_position()
        self.take_profit_box.update_button_position()
        self.stop_loss_box.update_button_position()

    def get_amount(self) -> Decimal:
        """Get amount."""
        return self.amount_box.value()

    def get_target_price(self) -> Decimal:
        """Get price."""
        return self.target_price_box.value()

    def get_take_profit(self) -> float:
        """Get take profit."""
        return self.take_profit_box.value()

    def get_stop_loss(self) -> float:
        """Get stop loss."""
        return self.stop_loss_box.value()
