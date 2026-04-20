# ruff: noqa: S101, PT027

"""Focused parity tests for native Orderly order builders."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
import unittest
from unittest.mock import AsyncMock, Mock

from httpx import HTTPStatusError, Request, Response

from plutus_terminal.core.exceptions import InvalidOrderSizeError, TransactionFailedError
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
        """Create a single TP child order using native POSITIONAL_TP_SL payloads."""
        # Arrange
        self.request_private.return_value = {"success": True}

        # Act
        await self.trader.create_reduce_order(
            _build_trade_arguments(
                trade_type=PerpsTradeType.TRIGGER_TP,
                reduce_only=True,
                take_profit=Decimal(99000),
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
        assert payload["algo_type"] == "POSITIONAL_TP_SL"
        assert "side" not in payload
        assert "quantity" not in payload
        assert len(payload["child_orders"]) == 1
        assert payload["child_orders"][0]["symbol"] == "PERP_BTC_USDC"
        assert payload["child_orders"][0]["algo_type"] == "TAKE_PROFIT"
        assert payload["child_orders"][0]["side"] == "SELL"
        assert payload["child_orders"][0]["type"] == "CLOSE_POSITION"
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
        """Create a single SL child order using native POSITIONAL_TP_SL payloads."""
        # Arrange
        self.request_private.return_value = {"success": True}

        # Act
        await self.trader.create_reduce_order(
            _build_trade_arguments(
                trade_type=PerpsTradeType.TRIGGER_SL,
                reduce_only=True,
                stop_loss=Decimal(94000),
            ),
        )

        # Assert
        call = self.request_private.await_args
        assert call is not None
        payload = call.kwargs["json_body"]
        assert payload["algo_type"] == "POSITIONAL_TP_SL"
        assert "side" not in payload
        assert len(payload["child_orders"]) == 1
        assert payload["child_orders"][0]["algo_type"] == "STOP_LOSS"
        assert payload["child_orders"][0]["side"] == "SELL"
        assert payload["child_orders"][0]["type"] == "CLOSE_POSITION"
        assert Decimal(payload["child_orders"][0]["trigger_price"]) == Decimal("94000.00")

    async def test_create_order_with_tp_sl_targets_submits_only_primary_regular_order(self) -> None:
        """Keep entry creation on the regular endpoint even when TP/SL intent is present."""
        # Arrange
        self.request_private.return_value = {"order_id": "primary"}

        # Act
        result = await self.trader.create_order(
            _build_trade_arguments(
                take_profit=Decimal(99000),
                stop_loss=Decimal(94000),
            ),
        )

        # Assert
        assert result == {"order_id": "primary"}
        assert self.request_private.await_count == 1
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("POST", "/v1/order")
        regular_payload = call.kwargs["json_body"]
        assert regular_payload["order_type"] == "LIMIT"
        assert Decimal(regular_payload["order_quantity"]) == Decimal("0.01")
        assert Decimal(regular_payload["order_price"]) == Decimal("97500.50")

    async def test_create_order_quantizes_tp_sl_targets_without_submitting_algo_request(
        self,
    ) -> None:
        """Normalize TP/SL targets on the request model without posting an algo order."""
        # Arrange
        self.request_private.return_value = {"order_id": "primary"}

        # Act
        await self.trader.create_order(
            _build_trade_arguments(
                take_profit=Decimal("99000.019"),
                stop_loss=Decimal("94000.019"),
            ),
        )

        # Assert
        payload = self.request_private.await_args.kwargs["json_body"]
        assert Decimal(payload["order_quantity"]) == Decimal("0.01")

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

    async def test_create_reduce_order_uses_regular_endpoint_for_reduce_only_limit_orders(
        self,
    ) -> None:
        """Keep reduce-only limit closes on the native regular endpoint."""
        # Arrange
        self.request_private.return_value = {"order_id": "reduce-limit"}

        # Act
        result = await self.trader.create_reduce_order(
            _build_trade_arguments(
                trade_type=PerpsTradeType.LIMIT,
                reduce_only=True,
            ),
        )

        # Assert
        assert result == {"order_id": "reduce-limit"}
        self.request_private.assert_awaited_once()
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("POST", "/v1/order")
        assert call.kwargs["json_body"]["reduce_only"] is True

    async def test_create_order_preserves_orderly_http_error_message_when_wrapped(self) -> None:
        """Expose the Orderly API error body instead of an empty transaction failure."""
        # Arrange
        request = Request("POST", "https://api.orderly.org/v1/order")
        response = Response(
            400,
            request=request,
            json={"code": -1102, "message": "order price is invalid"},
        )
        self.request_private.side_effect = HTTPStatusError(
            "Client error '400 Bad Request'",
            request=request,
            response=response,
        )

        # Act / Assert
        with self.assertRaisesRegex(TransactionFailedError, r"\[-1102\] order price is invalid"):
            await self.trader.create_order(_build_trade_arguments())

    async def test_create_order_rejects_final_notional_below_market_minimum(self) -> None:
        """Validate the final Orderly payload notional instead of the raw margin input."""
        # Arrange
        strict_rule = SimpleNamespace(
            base_min=Decimal(0),
            base_max=Decimal(1000),
            base_tick=Decimal("0.00000001"),
            quote_tick=Decimal("0.01"),
            min_notional=Decimal(25),
        )
        trader = OrderlyTrader(
            rest_client=cast(
                "OrderlyRestClient",
                SimpleNamespace(request_private=AsyncMock()),
            ),
            market_registry=cast(
                "OrderlyMarketRegistry",
                SimpleNamespace(get_rule_by_symbol=Mock(return_value=strict_rule)),
            ),
        )

        # Act / Assert
        with self.assertRaisesRegex(InvalidOrderSizeError, "Minimum is 25"):
            await trader.create_order(
                _build_trade_arguments(
                    size_stable=Decimal(10),
                ),
            )
