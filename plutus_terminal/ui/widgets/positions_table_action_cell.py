"""Action cell used by the positions table."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QWidget
from qasync import asyncSlot

from plutus_terminal.core.exchange.types import OrderData, PerpsTradeType
from plutus_terminal.ui.widgets.manage_order import ManageOrder
from plutus_terminal.ui.widgets.positions_table_close_action import PositionCloseAction

if TYPE_CHECKING:
    from plutus_terminal.controller.ui_controller import UIController
    from plutus_terminal.core.exchange.base import ExchangeBase
    from plutus_terminal.core.exchange.types import PerpsPosition


class PositionActionsCell(QWidget):
    """Widget used to manage a position from the positions table."""

    def __init__(
        self,
        position: PerpsPosition,
        exchange: ExchangeBase,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize widget."""
        super().__init__(parent)
        self._position = position
        self._exchange = exchange

        self._main_layout = QHBoxLayout()
        self.close_button = QPushButton("Close")
        self.tp_sl_button = QPushButton("TP/SL")

        self._menu = QMenu(self)
        self._close_action = PositionCloseAction(self._position, self)

        self._setup_widgets()
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """Configure widgets."""
        self._menu.setObjectName("floating")
        self._close_action.reduce_clicked.connect(self._on_close_reduce_clicked)
        self._close_action.set_price_clicked.connect(self.set_price_limit)
        self._menu.addAction(self._close_action)

        self.close_button.setProperty("class", "gray")
        self.close_button.setToolTip("Close Position. Right click for more options.")
        self.close_button.setMinimumSize(50, 30)
        self.close_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.close_button.customContextMenuRequested.connect(self.show_close_context)
        self.close_button.clicked.connect(self.close_position)

        self.tp_sl_button.setProperty("class", "gray")
        self.tp_sl_button.setToolTip("Open dialog to set TP/SL.")
        self.tp_sl_button.setMinimumSize(50, 30)
        self.tp_sl_button.clicked.connect(self.on_tp_sl_clicked)

    def _setup_layout(self) -> None:
        """Organize layouts."""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self.close_button)
        self._main_layout.addWidget(self.tp_sl_button)
        self.setLayout(self._main_layout)

    def set_position(self, position: PerpsPosition) -> None:
        """Update the widget to target a different position."""
        self._position = position
        self._close_action.set_position(position)

    def set_exchange(self, exchange: ExchangeBase) -> None:
        """Update the exchange dependency."""
        self._exchange = exchange

    def show_close_context(self, _pos: QPoint) -> None:
        """Show context menu."""
        self._menu.exec(self.close_button.mapToGlobal(self.close_button.rect().center()))

    def set_price_limit(self) -> None:
        """Set price for a limit close."""
        self._close_action.set_price_limit(
            self._exchange.cached_prices[self._position["pair"]]["price"],
        )

    @asyncSlot()
    async def close_position(self) -> None:
        """Close position."""
        await self._exchange.close_position(self._position)

    @asyncSlot()
    async def _on_close_reduce_clicked(self, kwargs: dict) -> None:
        """Handle click on reduce."""
        if self._position["position_size_stable"] == kwargs["size"]:
            await self._exchange.close_position(self._position)
            return

        kwargs["collateral_delta"] = (kwargs["size"] * self._position["collateral_stable"]) / (
            self._position["position_size_stable"]
        )
        await self._exchange.create_reduce_order(**kwargs)

    def on_tp_sl_clicked(self) -> None:
        """Handle click on TP/SL."""
        order_dialog = ManageOrder(
            OrderData(
                {
                    "pair": self._position["pair"],
                    "order_type": PerpsTradeType.TRIGGER_TP,
                    "size_stable": self._position["position_size_stable"],
                    "trigger_price": self._position["open_price"],
                    "id": "_",
                    "reduce_only": True,
                    "trade_direction": self._position["trade_direction"],
                },
            ),
            exchange=self._exchange,
            associated_position=deepcopy(self._position),
            parent=self,
        )
        order_dialog.execute_order.connect(self._handle_tp_sl_clicked)
        order_dialog.show()

    def _resolve_ui_controller(self) -> UIController | None:
        """Find the owning UI controller from the widget parent chain."""
        parent_widget = self.parentWidget()
        while parent_widget is not None:
            controller = getattr(parent_widget, "_ui_controller", None)
            if controller is not None:
                return controller
            parent_widget = parent_widget.parentWidget()
        return None

    def _collateral_delta_for_size(self, size_stable: Decimal) -> Decimal:
        """Resolve proportional collateral delta for partial reduce orders."""
        if size_stable == self._position["position_size_stable"]:
            return Decimal(0)
        return (size_stable * self._position["collateral_stable"]) / (
            self._position["position_size_stable"]
        )

    def _base_size_for_size(self, size_stable: Decimal) -> Decimal | None:
        """Resolve proportional native base size for the selected reduce amount."""
        position_extra = self._position.get("extra", {})
        if not isinstance(position_extra, dict):
            return None
        raw_base_size = position_extra.get("base_size")
        if raw_base_size in (None, ""):
            return None
        total_size = self._position["position_size_stable"]
        if total_size <= Decimal(0):
            return None
        return Decimal(str(raw_base_size)) * size_stable / total_size

    @asyncSlot(object)
    async def _handle_tp_sl_clicked(self, order_request: object) -> None:
        """Execute order on exchange."""
        if not isinstance(order_request, dict):
            return

        if "take_profit_price" in order_request or "stop_loss_price" in order_request:
            await self._handle_reduce_tp_sl_request(order_request)
            return

        order_data = cast("OrderData", order_request)
        collateral_delta = self._collateral_delta_for_size(order_data["size_stable"])

        await self._exchange.create_reduce_order(
            pair=order_data["pair"],
            size=order_data["size_stable"],
            collateral_delta=collateral_delta,
            trade_direction=order_data["trade_direction"],
            trade_type=order_data["order_type"],
            execution_price=order_data["trigger_price"],
        )

    async def _handle_reduce_tp_sl_request(self, order_request: object) -> None:
        """Forward native TP/SL request payload through the UI controller when available."""
        if not isinstance(order_request, dict):
            return

        request_payload = dict(order_request)
        reduce_size = Decimal(str(request_payload["size_stable"]))
        request_payload["collateral_delta"] = self._collateral_delta_for_size(reduce_size)
        base_size = self._base_size_for_size(reduce_size)
        if base_size is not None:
            request_payload["base_size"] = base_size

        ui_controller = self._resolve_ui_controller()
        if ui_controller is not None:
            await ui_controller.submit_position_tp_sl(request_payload)
            return

        take_profit_price = request_payload.get("take_profit_price")
        stop_loss_price = request_payload.get("stop_loss_price")
        trade_type = (
            PerpsTradeType.TRIGGER_TP
            if take_profit_price is not None
            else PerpsTradeType.TRIGGER_SL
        )
        raw_execution_price = (
            take_profit_price if take_profit_price is not None else stop_loss_price
        )
        if raw_execution_price is None:
            return
        execution_price = Decimal(str(raw_execution_price))
        await self._exchange.create_reduce_order(
            pair=str(request_payload["pair"]),
            size=Decimal(str(request_payload["size_stable"])),
            collateral_delta=Decimal(str(request_payload["collateral_delta"])),
            trade_direction=request_payload["trade_direction"],
            trade_type=trade_type,
            execution_price=execution_price,
        )
