# ruff: noqa: S101, PLR2004

"""Focused parity tests for native Orderly fetcher parsing behavior."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
import unittest
from unittest.mock import AsyncMock, Mock, patch

from plutus_terminal.core.exchange.orderly.fetcher import OrderlyFetcher
from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRegistry
from plutus_terminal.core.exchange.types import PerpsTradeDirection, PerpsTradeType

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient
    from plutus_terminal.core.exchange.orderly.websocket import OrderlyWebsocketManager
    from plutus_terminal.message_bus import MessageBus

_FIXTURES_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "orderly_fetcher_native_payloads.json"
)


def _build_market_registry() -> OrderlyMarketRegistry:
    registry = OrderlyMarketRegistry()
    registry.load_fallback_symbols(("PERP_BTC_USDC",))
    return registry


def _load_payloads() -> dict[str, Any]:
    return json.loads(_FIXTURES_PATH.read_text(encoding="utf-8"))


def _build_message_bus() -> SimpleNamespace:
    return SimpleNamespace(
        balance_fetched=SimpleNamespace(emit=Mock()),
        positions_fetched=SimpleNamespace(emit=Mock()),
        orders_fetched=SimpleNamespace(emit=Mock()),
        subscribed_prices_fetched=SimpleNamespace(emit=Mock()),
    )


class OrderlyFetcherParserParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify Orderly fetcher parsing matches native payload semantics."""

    def setUp(self) -> None:
        """Create deterministic fetcher dependencies for each test."""
        self.request_private = AsyncMock()
        self.websocket_manager = SimpleNamespace(
            has_public_topics=Mock(return_value=False),
            next_public_event=AsyncMock(),
            should_stop=Mock(return_value=False),
            subscribe_public=AsyncMock(),
            unsubscribe_public=AsyncMock(),
        )
        self.message_bus = _build_message_bus()
        self.fetcher = OrderlyFetcher(
            rest_client=cast(
                "OrderlyRestClient",
                SimpleNamespace(request_private=self.request_private),
            ),
            websocket_manager=cast("OrderlyWebsocketManager", self.websocket_manager),
            market_registry=_build_market_registry(),
            message_bus=cast("MessageBus", self.message_bus),
        )

    async def test_fetch_all_orders_parses_regular_stop_and_tp_sl_orders_with_trade_families(
        self,
    ) -> None:
        """Return regular, stop, and TP/SL child orders with native metadata preserved."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.side_effect = [
            {"data": {"rows": [payloads["regular_order"]]}},
            {"data": {"rows": [payloads["stop_algo_order"], payloads["tp_sl_algo_order"]]}},
        ]

        # Act
        orders = await self.fetcher.fetch_all_orders()

        # Assert
        assert len(orders) == 4
        orders_by_id = {order["id"]: order for order in orders}
        assert orders_by_id["12345"]["order_type"].order_family == "regular"
        assert orders_by_id["12345"]["order_type"] is PerpsTradeType.LIMIT
        assert orders_by_id["12345"]["trigger_price"] == Decimal("97500.5")
        assert orders_by_id["12345"]["size_stable"] == Decimal("975.005")
        regular_extra = cast("dict[str, str]", orders_by_id["12345"].get("extra", {}))
        assert Decimal(regular_extra["native_fee"]) == Decimal("0.585003")
        assert orders_by_id["54321"]["order_type"].order_family == "stop"
        assert orders_by_id["54321"]["order_type"] is PerpsTradeType.STOP_MARKET
        assert orders_by_id["54321"]["trade_direction"] is PerpsTradeDirection.LONG
        assert orders_by_id["54321"]["trigger_price"] == Decimal("95000")
        assert orders_by_id["54321"]["size_stable"] == Decimal("950")
        assert orders_by_id["60001"]["order_type"].order_family == "tp_sl"
        assert orders_by_id["60001"]["order_type"] is PerpsTradeType.TRIGGER_TP
        assert orders_by_id["60001"]["trigger_price"] == Decimal("99000")
        assert orders_by_id["60001"]["size_stable"] == Decimal("990")
        assert orders_by_id["60002"]["order_type"].order_family == "tp_sl"
        assert orders_by_id["60002"]["order_type"] is PerpsTradeType.TRIGGER_SL
        assert orders_by_id["60002"]["trigger_price"] == Decimal("94000")
        assert orders_by_id["60002"]["size_stable"] == Decimal("940")

    async def test_fetch_all_orders_filters_unknown_and_terminal_native_rows(self) -> None:
        """Drop rows that should not surface as active terminal orders."""
        # Arrange
        payloads = _load_payloads()
        closed_stop = payloads["stop_algo_order"] | {"algo_status": "TRIGGERED"}
        partial_tp_sl = payloads["tp_sl_algo_order"] | {
            "child_orders": [
                payloads["tp_sl_algo_order"]["child_orders"][0] | {"algo_status": "TRIGGERED"},
                payloads["tp_sl_algo_order"]["child_orders"][1],
            ],
        }
        unknown_regular = payloads["regular_order"] | {"symbol": "PERP_UNKNOWN_USDC"}
        self.request_private.side_effect = [
            {"data": {"rows": [unknown_regular]}},
            {"data": {"rows": [closed_stop, partial_tp_sl]}},
        ]

        # Act
        orders = await self.fetcher.fetch_all_orders()

        # Assert
        assert len(orders) == 1
        assert orders[0]["id"] == "60002"
        assert orders[0]["order_type"].order_family == "tp_sl"
        assert orders[0]["order_type"] is PerpsTradeType.TRIGGER_SL

    async def test_fetch_all_positions_prefers_native_liquidation_and_fee_fields(self) -> None:
        """Keep native liquidation and fee fields when parsing positions."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.return_value = {"data": {"rows": [payloads["position"]]}}

        # Act
        positions = await self.fetcher.fetch_all_positions()

        # Assert
        assert len(positions) == 1
        position = positions[0]
        assert position["pair"] == "Crypto.BTC/USDC"
        assert position["trade_direction"] is PerpsTradeDirection.LONG
        assert position["position_size_stable"] == Decimal("970")
        assert position["collateral_stable"] == Decimal("97")
        assert position["liquidation_price"] == Decimal("87456.12")
        assert self.fetcher.calculate_liquidation_price(position) == Decimal("87456.12")
        position_extra = cast("dict[str, str]", position.get("extra", {}))
        assert Decimal(position_extra["native_liquidation_price"]) == Decimal("87456.12")
        assert Decimal(position_extra["fee_24h"]) == Decimal("0.6")
        assert Decimal(position_extra["last_sum_unitary_funding"]) == Decimal("0.00001234")
        self.message_bus.balance_fetched.emit.assert_called_once_with(Decimal("5.005"))

    async def test_pnl_percent_prefers_native_unsettled_pnl_even_when_price_is_available(
        self,
    ) -> None:
        """Add opening fee back so exchange-level net PnL matches Orderly semantics."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.return_value = {"data": {"rows": [payloads["position"]]}}

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]
        pnl_percent = self.fetcher.calculate_pnl_percent_before_fees(
            position,
            Decimal("120000"),
        )

        # Assert
        assert pnl_percent == ((Decimal("5.005") + Decimal("0.582")) * Decimal(100)) / Decimal("97")

    async def test_fetch_funding_fee_uses_unsettled_pnl_gap_against_unrealized_pnl(
        self,
    ) -> None:
        """Derive current funding impact from the gap between unrealized and unsettled PnL."""
        # Arrange
        payloads = _load_payloads()
        position_payload = payloads["position"] | {"unsettled_pnl": "4.255"}
        self.request_private.return_value = {"data": {"rows": [position_payload]}}

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]

        # Assert
        assert self.fetcher.fetch_funding_fee(position) == Decimal("0.75")

    async def test_fetch_all_positions_skips_zero_quantity_rows(self) -> None:
        """Ignore empty native positions that should not surface in terminal state."""
        # Arrange
        payloads = _load_payloads()
        zero_quantity_position = payloads["position"] | {"position_qty": "0"}
        self.request_private.return_value = {"data": {"rows": [zero_quantity_position]}}

        # Act
        positions = await self.fetcher.fetch_all_positions()

        # Assert
        assert positions == []

    async def test_unsubscribe_to_price_skips_socket_work_when_pair_is_not_tracked(self) -> None:
        """Ignore unsubscribe requests for pairs without an active subscription count."""
        pair = "Crypto.BTC/USDC"
        self.fetcher._cached_prices[pair] = {  # noqa: SLF001
            "price": Decimal("1"),
            "date": cast("Any", None),
        }

        await self.fetcher.unsubscribe_to_price(pair)

        self.websocket_manager.unsubscribe_public.assert_not_awaited()
        assert self.fetcher._connection_count[pair] == 0  # noqa: SLF001
        assert pair not in self.fetcher._cached_prices  # noqa: SLF001

    async def test_receive_subscribed_prices_waits_for_public_topics_before_reading(self) -> None:
        """Avoid blocking on `next_public_event` before any public topic is active."""
        self.fetcher.start = AsyncMock()  # type: ignore[method-assign]
        self.websocket_manager.should_stop = Mock(side_effect=[False, True])

        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock:
            await self.fetcher.receive_subscribed_prices()

        self.fetcher.start.assert_awaited_once()  # type: ignore[attr-defined]
        self.websocket_manager.next_public_event.assert_not_awaited()
        sleep_mock.assert_awaited_once_with(0.1)
