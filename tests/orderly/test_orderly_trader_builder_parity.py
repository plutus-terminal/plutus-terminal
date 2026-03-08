# ruff: noqa: S101, PLR2004, PT027

"""Focused parity tests for native Orderly order builders."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
import unittest
from unittest.mock import AsyncMock

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRegistry
from plutus_terminal.core.exchange.orderly.trader import OrderlyTrader
from plutus_terminal.core.exchange.types import PerpsTradeDirection, PerpsTradeType

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient


def _build_market_registry() -> OrderlyMarketRegistry:
    registry = OrderlyMarketRegistry()
    registry.load_fallback_symbols(("PERP_BTC_USDC",))
    return registry


def _build_trade_arguments(**overrides: object) -> dict[str, object]:
    trade_arguments: dict[str, object] = {
        "symbol": "PERP_BTC_USDC",
        "trade_direction": PerpsTradeDirection.LONG,
        "trade_type": PerpsTradeType.LIMIT,
        "price": Decimal("97500.5"),
        "size_stable": Decimal("975.005"),
    }
    trade_arguments.update(overrides)
    return trade_arguments


class OrderlyTraderBuilderParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify trader behavior against native Orderly payload expectations."""

    def setUp(self) -> None:
        """Create deterministic trader dependencies for each test."""
        self.request_private = AsyncMock()
        self.trader = OrderlyTrader(
            rest_client=cast(
                "OrderlyRestClient",
                SimpleNamespace(request_private=self.request_private),
            ),
            market_registry=_build_market_registry(),
        )

    async def test_create_reduce_order_builds_single_take_profit_child_payload(self) -> None:
        """Create a single TP child order using native TP_SL payloads."""
        # Arrange
        self.request_private.return_value = {"success": True}

        # Act
        await self.trader.create_reduce_order(
            _build_trade_arguments(
                trade_type=PerpsTradeType.TRIGGER_TP,
                reduce_only=True,
                take_profit=Decimal("99000"),
            ),
        )

        # Assert
        assert self.request_private.await_count == 1
        call = self.request_private.await_args
        assert call is not None
        method, path = call.args[:2]
        payload = call.kwargs["json_body"]
        assert method == "POST"
        assert path == "/v1/algo/order"
        assert payload["side"] == "SELL"
        assert payload["algo_type"] == "TP_SL"
        assert Decimal(payload["quantity"]) == Decimal("0.01")
        assert len(payload["child_orders"]) == 1
        assert payload["child_orders"][0]["algo_type"] == "TAKE_PROFIT"
        assert Decimal(payload["child_orders"][0]["trigger_price"]) == Decimal("99000.00")

    async def test_create_reduce_order_raises_when_take_profit_target_is_missing(self) -> None:
        """Reject TP reduce orders that do not include a trigger target."""
        # Arrange
        self.request_private.return_value = {"success": True}

        # Act / Assert
        with self.assertRaises(TransactionFailedError):
            await self.trader.create_reduce_order(
                _build_trade_arguments(
                    trade_type=PerpsTradeType.TRIGGER_TP,
                    reduce_only=True,
                ),
            )

        assert self.request_private.await_count == 0

    async def test_create_reduce_order_builds_single_stop_loss_child_payload(self) -> None:
        """Create a single SL child order using native TP_SL payloads."""
        # Arrange
        self.request_private.return_value = {"success": True}

        # Act
        await self.trader.create_reduce_order(
            _build_trade_arguments(
                trade_type=PerpsTradeType.TRIGGER_SL,
                reduce_only=True,
                stop_loss=Decimal("94000"),
            ),
        )

        # Assert
        call = self.request_private.await_args
        assert call is not None
        payload = call.kwargs["json_body"]
        assert payload["side"] == "SELL"
        assert payload["algo_type"] == "TP_SL"
        assert len(payload["child_orders"]) == 1
        assert payload["child_orders"][0]["algo_type"] == "STOP_LOSS"
        assert Decimal(payload["child_orders"][0]["trigger_price"]) == Decimal("94000.00")

    async def test_create_order_submits_primary_order_and_paired_tp_sl_algo_request(self) -> None:
        """Submit a regular order plus a paired native TP/SL algo request."""
        # Arrange
        self.request_private.side_effect = [{"order_id": "primary"}, {"algo_order_id": "tp_sl"}]

        # Act
        result = await self.trader.create_order(
            _build_trade_arguments(
                take_profit=Decimal("99000"),
                stop_loss=Decimal("94000"),
            ),
        )

        # Assert
        assert result == {
            "primary": {"order_id": "primary"},
            "tp_sl": {"algo_order_id": "tp_sl"},
        }
        assert self.request_private.await_count == 2
        first_call = self.request_private.await_args_list[0]
        second_call = self.request_private.await_args_list[1]
        assert first_call.args[:2] == ("POST", "/v1/order")
        assert second_call.args[:2] == ("POST", "/v1/algo/order")
        regular_payload = first_call.kwargs["json_body"]
        tp_sl_payload = second_call.kwargs["json_body"]
        assert regular_payload["order_type"] == "LIMIT"
        assert Decimal(regular_payload["order_quantity"]) == Decimal("0.01")
        assert Decimal(regular_payload["order_price"]) == Decimal("97500.50")
        assert len(tp_sl_payload["child_orders"]) == 2
        assert {child["algo_type"] for child in tp_sl_payload["child_orders"]} == {
            "TAKE_PROFIT",
            "STOP_LOSS",
        }

    async def test_create_order_without_tp_sl_submits_only_the_primary_regular_order(self) -> None:
        """Keep regular order creation on the native regular endpoint without TP/SL targets."""
        # Arrange
        self.request_private.return_value = {"order_id": "primary"}

        # Act
        result = await self.trader.create_order(_build_trade_arguments())

        # Assert
        assert result == {"order_id": "primary"}
        assert self.request_private.await_count == 1
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("POST", "/v1/order")
