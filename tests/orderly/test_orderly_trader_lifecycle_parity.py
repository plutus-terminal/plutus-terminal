# ruff: noqa: S101, PLR2004, PT027

"""Focused parity tests for Orderly trader lifecycle behavior."""

from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, patch

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRegistry
from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRequestError
from plutus_terminal.core.exchange.orderly.trader import OrderlyTrader
from plutus_terminal.core.exchange.types import (
    PerpsTradeDirection,
    PerpsTradeType,
)

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


class OrderlyTraderLifecycleParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify trader lifecycle requests stay aligned with native Orderly behavior."""

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

    async def test_create_order_includes_deterministic_client_order_id_on_regular_orders(
        self,
    ) -> None:
        """Submit regular orders with a stable native client identifier."""
        # Arrange
        self.request_private.return_value = {"success": True, "data": {"order_id": "70001"}}

        with patch(
            "plutus_terminal.core.exchange.orderly.trader.uuid4",
            return_value=SimpleNamespace(hex="0123456789abcdef0123456789abcdef"),
        ):
            # Act
            result = await self.trader.create_order(_build_trade_arguments())

        # Assert
        assert result == {"success": True, "data": {"order_id": "70001"}}
        self.request_private.assert_awaited_once()
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("POST", "/v1/order")
        payload = call.kwargs["json_body"]
        assert payload["client_order_id"] == "plutus_0123456789abcdef01234567"
        assert Decimal(payload["order_price"]) == Decimal("97500.50")
        assert Decimal(payload["order_quantity"]) == Decimal("0.01")

    async def test_create_order_wraps_duplicate_client_order_rejection(self) -> None:
        """Surface duplicate open-order rejection through the trader error contract."""
        # Arrange
        self.request_private.side_effect = OrderlyRequestError.from_api_error(
            -1007,
            "duplicate data/request",
        )

        with patch(
            "plutus_terminal.core.exchange.orderly.trader.uuid4",
            return_value=SimpleNamespace(hex="fedcba9876543210fedcba9876543210"),
        ):
            # Act / Assert
            with self.assertRaises(TransactionFailedError) as error_context:
                await self.trader.create_order(_build_trade_arguments())

        self.request_private.assert_awaited_once()
        assert isinstance(error_context.exception.__cause__, OrderlyRequestError)
        assert "duplicate data/request" in str(error_context.exception.__cause__)

    async def test_cancel_order_hits_regular_delete_endpoint_and_preserves_cancel_sent_status(
        self,
    ) -> None:
        """Forward regular order cancels to the native delete endpoint unchanged."""
        # Arrange
        self.request_private.return_value = {
            "success": True,
            "data": {"status": "CANCEL_SENT", "order_id": "9001"},
        }

        # Act
        result = await self.trader.cancel_order(
            {
                "order_id": "9001",
                "symbol": "PERP_BTC_USDC",
                "trade_type": PerpsTradeType.LIMIT,
            },
        )

        # Assert
        assert result["data"]["status"] == "CANCEL_SENT"
        self.request_private.assert_awaited_once_with(
            "DELETE",
            "/v1/order",
            params={"order_id": "9001", "symbol": "PERP_BTC_USDC"},
        )

    async def test_cancel_order_wraps_not_found_failures_from_native_surface(
        self,
    ) -> None:
        """Report missing-order cancel failures on the stable transaction-error path."""
        # Arrange
        self.request_private.side_effect = OrderlyRequestError.from_api_error(
            -1006,
            "order not found",
        )

        # Act / Assert
        with self.assertRaises(TransactionFailedError) as error_context:
            await self.trader.cancel_order(
                {
                    "order_id": "missing-order",
                    "symbol": "PERP_BTC_USDC",
                    "trade_type": PerpsTradeType.LIMIT,
                },
            )

        self.request_private.assert_awaited_once_with(
            "DELETE",
            "/v1/order",
            params={"order_id": "missing-order", "symbol": "PERP_BTC_USDC"},
        )
        assert isinstance(error_context.exception.__cause__, OrderlyRequestError)
        assert "order not found" in str(error_context.exception.__cause__)

    async def test_edit_order_currently_replaces_order_via_cancel_then_create_instead_of_put(
        self,
    ) -> None:
        """Document the current replace-via-cancel flow instead of native PUT edit semantics."""
        # Arrange
        self.request_private.side_effect = [
            {"success": True, "data": {"status": "CANCEL_SENT", "order_id": "12345"}},
            {"success": True, "data": {"order_id": "54321", "status": "NEW"}},
        ]

        with patch(
            "plutus_terminal.core.exchange.orderly.trader.uuid4",
            return_value=SimpleNamespace(hex="00112233445566778899aabbccddeeff"),
        ):
            # Act
            result = await self.trader.edit_order(
                _build_trade_arguments(
                    order_id="12345",
                    reduce_only=False,
                ),
            )

        # Assert
        assert result == {
            "cancel": {
                "success": True,
                "data": {"status": "CANCEL_SENT", "order_id": "12345"},
            },
            "create": {"success": True, "data": {"order_id": "54321", "status": "NEW"}},
        }
        assert self.request_private.await_count == 2
        cancel_call = self.request_private.await_args_list[0]
        create_call = self.request_private.await_args_list[1]
        assert cancel_call.args[:2] == ("DELETE", "/v1/order")
        assert cancel_call.kwargs["params"] == {
            "order_id": "12345",
            "symbol": "PERP_BTC_USDC",
        }
        assert create_call.args[:2] == ("POST", "/v1/order")
        create_payload = create_call.kwargs["json_body"]
        assert create_payload["client_order_id"] == "plutus_00112233445566778899aabb"
        assert Decimal(create_payload["order_price"]) == Decimal("97500.50")

    async def test_edit_order_stops_after_cancel_failure_without_submitting_replacement_order(
        self,
    ) -> None:
        """Avoid sending a replacement create when the initial cancel fails."""
        # Arrange
        self.request_private.side_effect = OrderlyRequestError.from_api_error(
            -1006,
            "order not found",
        )

        # Act / Assert
        with self.assertRaises(TransactionFailedError):
            await self.trader.edit_order(
                _build_trade_arguments(
                    order_id="12345",
                    reduce_only=False,
                ),
            )

        self.request_private.assert_awaited_once_with(
            "DELETE",
            "/v1/order",
            params={"order_id": "12345", "symbol": "PERP_BTC_USDC"},
        )
