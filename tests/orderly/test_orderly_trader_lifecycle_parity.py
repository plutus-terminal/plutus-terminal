# ruff: noqa: S101, PLR2004, PT027

"""Focused parity tests for Orderly trader lifecycle behavior."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
import unittest
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

        with (
            patch(
                "plutus_terminal.core.exchange.orderly.trader.uuid4",
                return_value=SimpleNamespace(hex="fedcba9876543210fedcba9876543210"),
            ),
            self.assertRaises(TransactionFailedError) as error_context,
        ):
            # Act / Assert
            await self.trader.create_order(_build_trade_arguments())

        self.request_private.assert_awaited_once()
        assert isinstance(error_context.exception.__cause__, OrderlyRequestError)
        assert "duplicate data/request" in str(error_context.exception.__cause__)

    async def test_create_two_regular_orders_generates_distinct_client_order_ids(self) -> None:
        """Use a fresh client order id for each regular Orderly order submission."""
        # Arrange
        self.request_private.return_value = {"success": True}

        with patch(
            "plutus_terminal.core.exchange.orderly.trader.uuid4",
            side_effect=[
                SimpleNamespace(hex="0123456789abcdef0123456789abcdef"),
                SimpleNamespace(hex="fedcba9876543210fedcba9876543210"),
            ],
        ):
            # Act
            await self.trader.create_order(_build_trade_arguments())
            await self.trader.create_order(_build_trade_arguments(price=Decimal("97510.5")))

        # Assert
        assert self.request_private.await_count == 2
        first_payload = self.request_private.await_args_list[0].kwargs["json_body"]
        second_payload = self.request_private.await_args_list[1].kwargs["json_body"]
        assert first_payload["client_order_id"] == "plutus_0123456789abcdef01234567"
        assert second_payload["client_order_id"] == "plutus_fedcba9876543210fedcba98"
        assert first_payload["client_order_id"] != second_payload["client_order_id"]

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
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["data"]["status"] == "CANCEL_SENT"
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

    async def test_cancel_order_hits_algo_delete_endpoint_with_order_id_param(
        self,
    ) -> None:
        """Cancel algo orders through the native algo delete endpoint using `order_id`."""
        # Arrange
        self.request_private.return_value = {
            "success": True,
            "data": {"status": "CANCEL_SENT", "order_id": "tp-root"},
        }

        # Act
        result = await self.trader.cancel_order(
            {
                "order_id": "tp-root",
                "symbol": "PERP_BTC_USDC",
                "trade_type": PerpsTradeType.TRIGGER_TP,
            },
        )

        # Assert
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["data"]["status"] == "CANCEL_SENT"
        self.request_private.assert_awaited_once_with(
            "DELETE",
            "/v1/algo/order",
            params={
                "order_id": "tp-root",
                "symbol": "PERP_BTC_USDC",
            },
        )

    async def test_edit_order_uses_native_put_for_regular_orders(self) -> None:
        """Edit pending regular orders through Orderly native PUT semantics."""
        # Arrange
        self.request_private.return_value = {
            "success": True,
            "data": {"status": "EDIT_SENT", "order_id": "12345"},
        }

        # Act
        result = await self.trader.edit_order(
            _build_trade_arguments(
                order_id="12345",
                reduce_only=False,
            ),
        )

        # Assert
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["data"]["status"] == "EDIT_SENT"
        self.request_private.assert_awaited_once()
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("PUT", "/v1/order")
        payload = call.kwargs["json_body"]
        assert payload["order_id"] == "12345"
        assert payload["symbol"] == "PERP_BTC_USDC"
        assert payload["side"] == "BUY"
        assert payload["order_type"] == "LIMIT"
        assert Decimal(payload["order_quantity"]) == Decimal("0.01")
        assert Decimal(payload["order_price"]) == Decimal("97500.50")

    async def test_edit_order_uses_native_put_for_tp_sl_root_orders(self) -> None:
        """Edit TP/SL orders through the root algo order instead of replacing them."""
        # Arrange
        self.request_private.return_value = {
            "success": True,
            "data": {"status": "EDIT_SENT", "order_id": "root-1"},
        }

        # Act
        result = await self.trader.edit_order(
            _build_trade_arguments(
                order_id="root-1",
                root_algo_type="POSITIONAL_TP_SL",
                trade_type=PerpsTradeType.TRIGGER_TP,
                reduce_only=True,
                take_profit=Decimal(99000),
                stop_loss=Decimal(94000),
            ),
        )

        # Assert
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["data"]["status"] == "EDIT_SENT"
        self.request_private.assert_awaited_once()
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("PUT", "/v1/algo/order")
        payload = call.kwargs["json_body"]
        assert payload["order_id"] == "root-1"
        assert payload["algo_type"] == "POSITIONAL_TP_SL"
        assert "side" not in payload
        assert "quantity" not in payload
        assert {child["algo_type"] for child in payload["child_orders"]} == {
            "TAKE_PROFIT",
            "STOP_LOSS",
        }
        assert {child["type"] for child in payload["child_orders"]} == {"CLOSE_POSITION"}

    async def test_edit_order_wraps_native_put_failures_without_replacing_the_order(
        self,
    ) -> None:
        """Report native PUT failures without sending follow-up create requests."""
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

        self.request_private.assert_awaited_once()
        call = self.request_private.await_args
        assert call is not None
        assert call.args[:2] == ("PUT", "/v1/order")
        assert call.kwargs["json_body"]["order_id"] == "12345"
