# ruff: noqa: SLF001

"""Focused parity tests for position close action routing."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from PySide6 import QtWidgets

from plutus_terminal.core.exchange.types import PerpsTradeDirection, PerpsTradeType
from plutus_terminal.ui.widgets.positions_table_action_cell import PositionActionsCell


class OrderlyPositionActionsParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify limit and market close actions keep their distinct execution paths."""

    @classmethod
    def setUpClass(cls) -> None:
        """Ensure one QApplication exists for widget tests."""
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self) -> None:
        """Create a position widget with exchange stubs for each test."""
        self.position = {
            "pair": "Crypto.BTC/USDC",
            "position_size_stable": Decimal(100),
            "collateral_stable": Decimal(20),
            "trade_direction": PerpsTradeDirection.LONG,
        }
        self.exchange = SimpleNamespace(
            cached_prices={"Crypto.BTC/USDC": {"price": Decimal("97500.5")}},
            close_position=AsyncMock(),
            create_reduce_order=AsyncMock(),
        )
        self.widget = PositionActionsCell(self.position, self.exchange)

    async def test_full_size_limit_close_stays_on_reduce_order_flow(self) -> None:
        """Submit a full-size limit close as a reduce-only order instead of a market close."""
        # Arrange
        kwargs = {
            "pair": "Crypto.BTC/USDC",
            "size": Decimal(100),
            "trade_direction": PerpsTradeDirection.LONG,
            "trade_type": PerpsTradeType.LIMIT,
            "execution_price": Decimal(98000),
        }

        # Act
        await self.widget._on_close_reduce_clicked(kwargs)

        # Assert
        self.exchange.close_position.assert_not_awaited()
        self.exchange.create_reduce_order.assert_awaited_once_with(
            pair="Crypto.BTC/USDC",
            size=Decimal(100),
            trade_direction=PerpsTradeDirection.LONG,
            trade_type=PerpsTradeType.LIMIT,
            execution_price=Decimal(98000),
            collateral_delta=Decimal(20),
        )

    async def test_full_size_market_close_keeps_immediate_close_behavior(self) -> None:
        """Preserve the market close shortcut for full-position exits."""
        # Arrange
        kwargs = {
            "pair": "Crypto.BTC/USDC",
            "size": Decimal(100),
            "trade_direction": PerpsTradeDirection.LONG,
            "trade_type": PerpsTradeType.MARKET,
            "execution_price": None,
        }

        # Act
        await self.widget._on_close_reduce_clicked(kwargs)

        # Assert
        self.exchange.close_position.assert_awaited_once_with(self.position)
        self.exchange.create_reduce_order.assert_not_awaited()
