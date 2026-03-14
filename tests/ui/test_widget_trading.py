# ruff: noqa: S101, SLF001

"""Unit tests for trading, news, and chart widgets."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Self
from unittest.mock import Mock, patch

import pandas
from PySide6 import QtCore, QtGui, QtWidgets

from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType
from plutus_terminal.ui.widgets.account_info import AccountInfo
from plutus_terminal.ui.widgets.manage_order import ManageOrder
from plutus_terminal.ui.widgets.news_list import NewsList
from plutus_terminal.ui.widgets.news_widget import ClickableGroupBox, NewsWidget
from plutus_terminal.ui.widgets.orders_table_action_cell import OrderActionsCell
from plutus_terminal.ui.widgets.orders_table_columns import get_order_column_index
from plutus_terminal.ui.widgets.orders_table_state import get_order_identity_key, get_order_row_key
from plutus_terminal.ui.widgets.perps_trade import (
    LimitTradeWidget,
    MarketTradeWidget,
    PerpsTradeWidget,
    StopTradeWidget,
)
from plutus_terminal.ui.widgets.pnl_breakdown import PnlBreakdown
from plutus_terminal.ui.widgets.positions_table_action_cell import PositionActionsCell
from plutus_terminal.ui.widgets.positions_table_liquidation_cell import LiquidationPriceCell
from plutus_terminal.ui.widgets.trade_table import TradeTable
from plutus_terminal.ui.widgets.trading_chart import SearchPairModal, TradingChart, VimLineEdit
from tests.ui.helpers import (
    ExchangeStub,
    UIControllerStub,
    build_news_data,
    build_order,
    build_position,
    create_closed_task,
    ensure_app,
    process_events,
    run_async,
)

ensure_app()


class _FakeLine:
    """Minimal chart line stub."""

    def __init__(self, price: float) -> None:
        self.price = price
        self.deleted = False

    def update(self, price: float) -> None:
        self.price = price

    def delete(self) -> None:
        self.deleted = True


class _RaisingDeletedLine(_FakeLine):
    """Chart line stub that raises once invalidated."""

    def __init__(self, price: float) -> None:
        super().__init__(price)
        self.invalidated = False

    def update(self, price: float) -> None:
        if self.invalidated:
            msg = "stale line"
            raise RuntimeError(msg)
        super().update(price)

    def delete(self) -> None:
        if self.invalidated:
            msg = "stale line"
            raise RuntimeError(msg)
        super().delete()


class _FakeTopBarField:
    """Minimal chart topbar field stub."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


class _FakeTopBar:
    """Minimal chart topbar namespace."""

    def __init__(self) -> None:
        self._fields = {"pair": _FakeTopBarField(), "timeframe": _FakeTopBarField("1min")}

    def textbox(self, name: str) -> None:
        self._fields[name] = _FakeTopBarField()

    def switcher(self, name: str, _options: tuple[str, ...], default: str, func: object) -> None:
        self._fields[name] = _FakeTopBarField(default)
        self.func = func

    def __getitem__(self, key: str) -> _FakeTopBarField:
        return self._fields[key]


class _FakeEvents:
    """Minimal chart events namespace."""

    def __init__(self) -> None:
        self.range_change = self
        self.callbacks: list[object] = []

    def __iadd__(self, callback: object) -> Self:
        self.callbacks.append(callback)
        return self


class _FakeToolbox:
    """Minimal chart toolbox namespace."""

    def __init__(self) -> None:
        self.drawings: list[object] = []
        self.saved_under = ""

    def save_drawings_under(self, storage: object) -> None:
        self.saved_under = getattr(storage, "tag", "")

    def load_drawings(self, _tag: str) -> None:
        return

    def reposition_on_time(self) -> None:
        return


class _FakeQtChart:
    """Minimal lightweight-charts stand-in for unit tests."""

    def __init__(self, toolbox: bool = True) -> None:
        self.toolbox = _FakeToolbox() if toolbox else None
        self.topbar = _FakeTopBar()
        self.events = _FakeEvents()
        self.candle_data = None
        self.precision_value = 0
        self.webview = QtWidgets.QWidget()
        self.lines: list[_FakeLine] = []

    def precision(self, value: int) -> None:
        self.precision_value = value

    def layout(self, **_kwargs: object) -> None:
        return

    def legend(self, **_kwargs: object) -> None:
        return

    def get_webview(self) -> QtWidgets.QWidget:
        return self.webview

    def set(self, data: pandas.DataFrame, keep_drawings: bool = False) -> None:
        self.candle_data = data.rename(columns={"date": "time"})
        self.keep_drawings = keep_drawings

    def update(self, ohlcv: object) -> None:
        self.updated = ohlcv

    def update_from_tick(self, tick: object) -> None:
        self.last_tick = tick

    def price_scale(self) -> None:
        return

    def fit(self) -> None:
        self.fitted = True

    def horizontal_line(self, price: float, **_kwargs: object) -> _FakeLine:
        line = _FakeLine(price)
        self.lines.append(line)
        return line


class _ResetInvalidatingQtChart(_FakeQtChart):
    """Fake chart that invalidates existing lines after set()."""

    def set(self, data: pandas.DataFrame, keep_drawings: bool = False) -> None:
        for line in self.lines:
            if isinstance(line, _RaisingDeletedLine):
                line.invalidated = True
        super().set(data, keep_drawings=keep_drawings)

    def horizontal_line(self, price: float, **_kwargs: object) -> _RaisingDeletedLine:
        line = _RaisingDeletedLine(price)
        self.lines.append(line)
        return line


class _ImmediateTask:
    """Minimal task double that runs the coroutine immediately in tests."""

    def __init__(self, coroutine: object) -> None:
        self._exception: Exception | None = None
        try:
            asyncio.run(coroutine)
        except RuntimeError as error:  # pragma: no cover - exercised via callback path
            self._exception = error

    def add_done_callback(self, callback: object) -> None:
        callback(self)

    def cancelled(self) -> bool:
        return False

    def exception(self) -> Exception | None:
        return self._exception


def test_account_info_refreshes_balance_summary() -> None:
    """AccountInfo should render the grouped balance summary and details."""
    controller = UIControllerStub()
    widget = AccountInfo(controller)

    controller.message_bus.balance_fetched.emit(Decimal("0"))

    assert widget._balance_value.text() == "$200.000 USD"
    assert widget._toggle_details_button.text() == "Show Balance Details"


def test_perps_trade_widget_percent_button_sets_amount() -> None:
    """Percent shortcuts should size trades from the available balance."""
    controller = UIControllerStub()
    widget = PerpsTradeWidget(controller)
    market = widget._trade_type_market
    first_button = market.percent_group.button(25)

    widget._handle_percent_button_click(first_button)

    assert market.amount_box.value() == Decimal("50")


def test_market_limit_and_stop_widgets_return_current_values() -> None:
    """Standalone trade entry widgets should expose their entered values."""
    take_profit = 1.5
    stop_loss = 0.5
    market = MarketTradeWidget("USDC")
    market.amount_box.setValue(Decimal("12"))
    market.take_profit_box.setValue(take_profit)
    market.stop_loss_box.setValue(stop_loss)
    limit = LimitTradeWidget("USDC")
    limit.amount_box.setValue(Decimal("9"))
    limit.target_price_box.setValue(Decimal("100"))
    stop = StopTradeWidget("USDC")
    stop.amount_box.setValue(Decimal("7"))
    stop.trigger_price_box.setValue(Decimal("88"))

    assert market.get_amount() == Decimal("12")
    assert market.get_take_profit() == take_profit
    assert market.get_stop_loss() == stop_loss
    assert limit.get_amount() == Decimal("9")
    assert limit.get_target_price() == Decimal("100")
    assert stop.get_amount() == Decimal("7")
    assert stop.get_trigger_price() == Decimal("88")


def test_liquidation_price_cell_formats_price() -> None:
    """Liquidation cell should render an orange formatted price label."""
    cell = LiquidationPriceCell()

    cell.set_price(Decimal("1234.567"))

    assert "$1,234.567" in cell._price_label.text()


def test_pnl_breakdown_builds_fee_tooltip() -> None:
    """PnL breakdown tooltips should include fees and net pnl labels."""
    breakdown = PnlBreakdown()
    breakdown.set_pnl(Decimal("10"), Decimal("5"))
    breakdown.set_tooltip_content(
        Decimal("12"),
        Decimal("1"),
        Decimal("2"),
        Decimal("3"),
        Decimal("6"),
        funding_fee_included=True,
        labels=("Gross PnL", "Net PnL"),
        push_tool_tip=False,
    )

    assert "Gross PnL: 12" in breakdown.toolTip()
    assert "Funding Fee (included): -1" in breakdown.toolTip()
    assert "Net PnL: 6" in breakdown.toolTip()


def test_manage_order_builds_paired_reduce_request() -> None:
    """ManageOrder should emit paired TP/SL payloads for reduce-only orders."""
    order = build_order(order_type=PerpsTradeType.TRIGGER_TP, reduce_only=True)
    position = build_position()
    dialog = ManageOrder(order, ExchangeStub(), position)
    dialog._pair_order_checkbox.setChecked(True)
    dialog.trigger_box.setValue(Decimal("110000"))
    dialog.secondary_trigger_box.setValue(Decimal("95000"))

    payload = dialog._build_reduce_order_request()

    assert payload is not None
    assert payload["take_profit_price"] == Decimal("110000")
    assert payload["stop_loss_price"] == Decimal("95000")


def test_manage_order_warns_for_invalid_reduce_trigger() -> None:
    """Reduce-only TP/SL validation should reject unprofitable trigger prices."""
    order = build_order(order_type=PerpsTradeType.TRIGGER_TP, reduce_only=True)
    position = build_position()
    dialog = ManageOrder(order, ExchangeStub(), position)
    dialog.trigger_box.setValue(Decimal("90000"))

    with patch("PySide6.QtWidgets.QMessageBox.warning") as warning:
        payload = dialog._build_reduce_order_request()

    assert payload is None
    warning.assert_called_once()


def test_position_actions_cell_routes_tp_sl_request_to_ui_controller() -> None:
    """Position action cells should prefer the owning UI controller for TP/SL flows."""
    controller = UIControllerStub()
    parent = QtWidgets.QWidget()
    parent._ui_controller = controller
    cell = PositionActionsCell(build_position(), controller.current_exchange, parent=parent)

    run_async(
        cell._handle_tp_sl_clicked,
        {
            "pair": "Crypto.BTC/USDC",
            "size_stable": Decimal("50"),
            "trade_direction": PerpsTradeDirection.LONG,
            "take_profit_price": Decimal("110000"),
            "stop_loss_price": Decimal("95000"),
            "reference_price": Decimal("110000"),
        },
    )

    assert controller.submitted_tp_sl
    assert controller.submitted_tp_sl[0]["base_size"] == Decimal("0.0005")


def test_order_actions_cell_edits_order_using_exchange() -> None:
    """Order action cells should forward edited order values to the exchange."""
    exchange = ExchangeStub()
    cell = OrderActionsCell(build_order(), exchange)

    run_async(
        cell._edit_order,
        {
            **build_order(),
            "size_stable": Decimal("75"),
            "trigger_price": Decimal("101000"),
        },
    )

    assert exchange.edited_orders[0]["new_size_stable"] == Decimal("75")
    assert exchange.edited_orders[0]["new_execution_price"] == Decimal("101000")


def test_trade_table_updates_tabs_and_refreshes_liquidation_column() -> None:
    """Trade table should track tab counts and coalesced liquidation refreshes."""
    controller = UIControllerStub()
    widget = TradeTable(controller)
    widget._positions_table.refresh_liquidation_prices = Mock()

    widget.update_positions([build_position()])
    widget.update_orders([build_order()])
    widget._refresh_liquidation_column()

    assert widget._tab_widget.tabText(0) == "Positions (1)"
    assert widget._tab_widget.tabText(1) == "Orders (1)"
    widget._positions_table.refresh_liquidation_prices.assert_called_once()


def test_trade_table_keeps_distinct_action_cells_for_same_pair_orders() -> None:
    """Orders with colliding ids should still keep distinct action widgets and targets."""
    controller = UIControllerStub()
    widget = TradeTable(controller)
    older_order = build_order(
        order_id="",
        trigger_price=Decimal("100000"),
        extra={"client_order_id": "client-old", "updated_time": "1"},
    )
    newer_order = build_order(
        order_id="",
        trigger_price=Decimal("101000"),
        extra={"client_order_id": "client-new", "updated_time": "2"},
    )

    widget.update_orders([newer_order, older_order])
    process_events()

    buttons_column = get_order_column_index("buttons")
    first_cell = widget._orders_table.indexWidget(widget._orders_model.index(0, buttons_column))
    second_cell = widget._orders_table.indexWidget(widget._orders_model.index(1, buttons_column))

    assert isinstance(first_cell, OrderActionsCell)
    assert isinstance(second_cell, OrderActionsCell)
    assert first_cell is not second_cell

    run_async(second_cell.cancel_order)

    assert controller.current_exchange.cancelled_orders[0]["trigger_price"] == Decimal("100000")


def test_trade_table_cancel_survives_row_removal_during_inflight_close() -> None:
    """Canceling one row should survive the table reset that removes that same row."""
    controller = UIControllerStub()
    widget = TradeTable(controller)
    older_order = build_order(order_id="older", trigger_price=Decimal("100000"))
    newer_order = build_order(order_id="newer", trigger_price=Decimal("101000"))
    widget.update_orders([newer_order, older_order])
    process_events()

    observed: list[dict[str, object]] = []

    async def _cancel_order(order_data: dict[str, object]) -> None:
        observed.append(order_data)
        widget.update_orders([newer_order])

    controller.current_exchange.cancel_order = _cancel_order

    buttons_column = get_order_column_index("buttons")
    older_cell = widget._orders_table.indexWidget(widget._orders_model.index(1, buttons_column))

    assert isinstance(older_cell, OrderActionsCell)

    with patch(
        "plutus_terminal.ui.widgets.orders_table_action_cell.asyncio.create_task",
        side_effect=_ImmediateTask,
    ):
        older_cell._on_cancel_order()
    process_events()

    assert observed[0]["id"] == "older"
    assert widget._orders_model.rowCount() == 1


def test_trade_table_coalesces_bursty_order_updates() -> None:
    """Only the latest burst snapshot should reach the orders model."""
    controller = UIControllerStub()
    widget = TradeTable(controller)
    widget._orders_model.update_orders = Mock()
    first_orders = [build_order(order_id="first")]
    second_orders = [build_order(order_id="second")]

    widget._schedule_order_refresh(first_orders)
    widget._schedule_order_refresh(second_orders)
    widget._flush_order_refresh()

    widget._orders_model.update_orders.assert_called_once_with(second_orders)
    assert widget._tab_widget.tabText(1) == "Orders (1)"


def test_trade_table_recreates_deleted_cached_action_cell() -> None:
    """A cached but deleted order-action cell should be recreated on the next sync."""
    controller = UIControllerStub()
    widget = TradeTable(controller)
    older_order = build_order(
        order_id="",
        trigger_price=Decimal("100000"),
        extra={"client_order_id": "client-old", "updated_time": "1"},
    )
    newer_order = build_order(
        order_id="",
        trigger_price=Decimal("101000"),
        extra={"client_order_id": "client-new", "updated_time": "2"},
    )

    widget.update_orders([newer_order, older_order])
    process_events()

    buttons_column = get_order_column_index("buttons")
    first_index = widget._orders_model.index(0, buttons_column)
    first_cell = widget._orders_table.indexWidget(first_index)

    assert isinstance(first_cell, OrderActionsCell)

    first_cell.hide()
    first_cell.setParent(None)
    first_cell.deleteLater()
    process_events()

    widget.update_orders([newer_order, older_order])
    process_events()

    recreated_cell = widget._orders_table.indexWidget(first_index)
    second_cell = widget._orders_table.indexWidget(widget._orders_model.index(1, buttons_column))

    assert isinstance(recreated_cell, OrderActionsCell)
    assert isinstance(second_cell, OrderActionsCell)


def test_trade_table_prunes_deleted_cached_action_cell_without_crashing() -> None:
    """Pruning stale rows should ignore cached widgets whose C++ object is already gone."""
    controller = UIControllerStub()
    widget = TradeTable(controller)
    older_order = build_order(order_id="older", trigger_price=Decimal("100000"))
    newer_order = build_order(order_id="newer", trigger_price=Decimal("101000"))

    widget.update_orders([newer_order, older_order])
    process_events()

    buttons_column = get_order_column_index("buttons")
    older_index = widget._orders_model.index(1, buttons_column)
    older_cell = widget._orders_table.indexWidget(older_index)

    assert isinstance(older_cell, OrderActionsCell)

    older_cell.hide()
    older_cell.setParent(None)
    older_cell.deleteLater()
    process_events()

    widget.update_orders([newer_order])
    process_events()

    assert widget._orders_model.rowCount() == 1


def test_order_identity_key_distinguishes_same_pair_orders_with_blank_ids() -> None:
    """Fallback identity keys should keep multiple same-pair orders distinct in the UI."""
    older_order = build_order(
        order_id="",
        trigger_price=Decimal("100000"),
        extra={"client_order_id": "client-old", "updated_time": "1"},
    )
    newer_order = build_order(
        order_id="",
        trigger_price=Decimal("101000"),
        extra={"client_order_id": "client-new", "updated_time": "2"},
    )

    assert get_order_identity_key(older_order) != get_order_identity_key(newer_order)
    assert get_order_row_key(older_order) != get_order_row_key(newer_order)


def test_news_list_replaces_selected_widget_on_update() -> None:
    """News list updates should swap the existing widget in place."""
    controller = UIControllerStub(news_items=[])
    widget = NewsList(controller)

    class _FakeNewsWidget(QtWidgets.QLabel):
        def __init__(self, news_data: dict[str, object]) -> None:
            super().__init__(str(news_data["news_id"]))
            self.news_data = news_data
            self.display_delay = False

        def set_selected_style(self) -> None:
            self.selected = True

        def set_unselected_style(self) -> None:
            self.selected = False

        def stop_async(self) -> None:
            return

        def open_link(self) -> None:
            return

    def _create_news_widget(
        news_data: dict[str, object], display_delay: bool = False
    ) -> _FakeNewsWidget:
        del display_delay
        return _FakeNewsWidget(news_data)

    widget._sfxs = {":/sfx/test": Mock(play=Mock())}
    widget._create_news_widget = _create_news_widget
    initial = build_news_data(news_id="n-1")
    updated = build_news_data(news_id="n-1", title="Updated")
    widget._add_news_to_list(initial, display_delay=False)

    widget.update_news(updated)

    assert widget._scroll_layout.count() == 1
    assert widget._news_widgets["n-1"].news_data["title"] == "Updated"


def test_news_widget_updates_trade_button_values() -> None:
    """NewsWidget should refresh both long and short quick-trade labels."""
    controller = UIControllerStub()
    news_widget = NewsWidget(
        build_news_data(coin={"BTC"}),
        controller.current_exchange.format_pair_from_coin,
        controller.current_exchange.available_pairs,
        display_delay=False,
        app_config=controller.app_config,
    )
    with patch(
        "plutus_terminal.ui.widgets.news_widget.asyncio.create_task",
        side_effect=create_closed_task,
    ):
        news_widget.create_interactions(controller.current_exchange)

    controller.app_config.trade_value_lowest = 11
    controller.app_config.trade_value_low = 22
    controller.app_config.trade_value_medium = 33
    controller.app_config.trade_value_high = 44
    news_widget.update_trade_buttons()

    assert news_widget.findChildren(QtWidgets.QPushButton, "LONG_0")[0].text() == "$11"
    assert news_widget.findChildren(QtWidgets.QPushButton, "SHORT_3")[0].text() == "-$44"


def test_clickable_group_box_emits_click_signal() -> None:
    """Clickable group boxes should emit their custom click signal on press."""
    group = ClickableGroupBox("BTC")
    observed: list[str] = []
    group.clicked.connect(lambda: observed.append("clicked"))

    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(1, 1),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    group.mousePressEvent(event)

    assert observed == ["clicked"]


def test_trading_chart_updates_pair_text_and_tick_label() -> None:
    """TradingChart should react to pair text changes and live ticks."""
    controller = UIControllerStub()
    with patch("plutus_terminal.ui.widgets.trading_chart.QtChart", _FakeQtChart):
        chart = TradingChart(controller)
        chart.main_chart.candle_data = pandas.DataFrame({"time": [1]})
        chart.set_pair_text("Crypto.ETH/USDC")
        chart.update_chart_tick(
            {
                "Crypto.BTC/USDC": {
                    "price": Decimal("99999.5"),
                    "date": QtCore.QDateTime.currentDateTimeUtc().toSecsSinceEpoch(),
                }
            }
        )

    assert chart.top_bar.title.text() == "Chart | ETH/USDC"
    assert "$99,999.5" in chart._price_label.text()


def test_trading_chart_handles_multi_order_refresh_after_chart_reset() -> None:
    """Chart order overlays should survive a reset followed by multi-order refreshes."""
    controller = UIControllerStub()
    with patch("plutus_terminal.ui.widgets.trading_chart.QtChart", _ResetInvalidatingQtChart):
        chart = TradingChart(controller)
        orders = [
            build_order(order_id="first", trigger_price=Decimal("100000")),
            build_order(order_id="second", trigger_price=Decimal("101000")),
        ]
        history = pandas.DataFrame({"date": [pandas.Timestamp("2024-01-01")], "close": [1]})

        chart.draw_orders(orders)
        chart.set_start_data(history)
        chart.draw_orders(orders)
        chart.draw_orders([orders[1]])

    assert list(chart._order_lines) == [get_order_identity_key(orders[1])]


def test_search_pair_modal_emits_selected_pair() -> None:
    """Search modal should resolve display pairs back to exchange pairs."""
    parent = QtWidgets.QWidget()
    parent.resize(500, 300)
    controller = UIControllerStub()
    modal = SearchPairModal(controller, parent)
    observed: list[str] = []
    modal.pair_selected.connect(observed.append)
    modal.search_input.setText("BTC/USDC")

    modal.on_search_pair()

    assert observed == ["Crypto.BTC/USDC"]


def test_vim_line_edit_posts_popup_navigation_event() -> None:
    """Ctrl-J should navigate the completer popup like a down-arrow press."""
    completer = QtWidgets.QCompleter(["BTC/USDC", "ETH/USDC"])
    line_edit = VimLineEdit(completer)
    with patch("PySide6.QtWidgets.QApplication.postEvent") as post_event:
        event = QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress,
            QtCore.Qt.Key.Key_J,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        line_edit.keyPressEvent(event)

    post_event.assert_called_once()
