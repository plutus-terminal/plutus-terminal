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
        self.request_public = AsyncMock(return_value={"data": {"rows": []}})
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
                SimpleNamespace(
                    request_private=self.request_private,
                    request_public=self.request_public,
                ),
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

    async def test_fetch_all_orders_uses_client_order_id_when_native_regular_id_is_missing(
        self,
    ) -> None:
        """Keep same-pair regular orders distinct even if native order_id is absent."""
        # Arrange
        payloads = _load_payloads()
        first_order = payloads["regular_order"] | {
            "order_id": "",
            "client_order_id": "plutus_regular_a",
            "price": "97500.5",
        }
        second_order = payloads["regular_order"] | {
            "order_id": "",
            "client_order_id": "plutus_regular_b",
            "price": "97600.5",
            "updated_time": 1710000000001,
        }
        self.request_private.side_effect = [
            {"data": {"rows": [first_order, second_order]}},
            {"data": {"rows": []}},
        ]

        # Act
        orders = await self.fetcher.fetch_all_orders()

        # Assert
        assert [order["id"] for order in orders] == ["plutus_regular_b", "plutus_regular_a"]
        first_extra = cast("dict[str, str]", orders[0].get("extra", {}))
        second_extra = cast("dict[str, str]", orders[1].get("extra", {}))
        assert first_extra["client_order_id"] == "plutus_regular_b"
        assert second_extra["client_order_id"] == "plutus_regular_a"

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
        assert position_extra["timestamp"] == "1710000000000"
        self.message_bus.balance_fetched.emit.assert_called_once_with(Decimal("0"))

    async def test_fetch_unsettled_pnl_scales_with_selected_position_size(
        self,
    ) -> None:
        """Scale native unsettled PnL for partial-close estimates."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.return_value = {"data": {"rows": [payloads["position"]]}}

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]
        partial_position = cast("Any", position | {"position_size_stable": Decimal("485")})

        # Assert
        assert self.fetcher.fetch_unsettled_pnl(partial_position) == Decimal("2.5025")

    async def test_fetch_funding_fee_uses_sum_unitary_funding_delta_and_scales_for_partial_close(
        self,
    ) -> None:
        """Use the same funding accumulator delta formula as the React SDK."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.return_value = {"data": {"rows": [payloads["position"]]}}
        self.request_public.return_value = {
            "data": {
                "rows": [
                    {
                        "symbol": "PERP_BTC_USDC",
                        "sum_unitary_funding": "75.00001234",
                    },
                ],
            },
        }

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]
        partial_position = cast("Any", position | {"position_size_stable": Decimal("485")})

        # Assert
        assert self.fetcher.fetch_funding_fee(partial_position) == Decimal("0.375")

    async def test_fetch_opening_fee_uses_cached_trade_history_fee_and_scales_for_partial_close(
        self,
    ) -> None:
        """Use reconstructed current-leg fees for open positions when trade history is available."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.side_effect = [
            {"data": {"rows": [payloads["position"]]}},
            {
                "data": {
                    "rows": [
                        {
                            "side": "BUY",
                            "executed_quantity": "0.01",
                            "executed_price": "97000",
                            "fee": "0.582",
                            "fee_asset": "USDC",
                            "executed_timestamp": 1710000000100,
                        },
                    ],
                    "meta": {"total": 1, "records_per_page": 500, "current_page": 1},
                },
            },
        ]

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]
        partial_position = cast("Any", position | {"position_size_stable": Decimal("485")})

        # Assert
        assert self.fetcher.fetch_opening_fee(partial_position) == Decimal("0.2910")

    def test_fetch_opening_fee_falls_back_to_margin_estimate_without_cached_trade_history(
        self,
    ) -> None:
        """Fallback opening fees should match the entry-notional fee preview when no cache exists."""
        # Arrange
        position = {
            "pair": "Crypto.BTC/USDC",
            "id": 77,
            "position_size_stable": Decimal("970"),
            "collateral_stable": Decimal("97"),
            "open_price": Decimal("97000"),
            "trade_direction": PerpsTradeDirection.LONG,
            "leverage": Decimal("10"),
            "liquidation_price": Decimal("87456.12"),
            "extra": {
                "symbol": "PERP_BTC_USDC",
                "raw_cost_position": "970.582",
                "native_notional": "970",
                "base_size": "0.01",
            },
        }

        # Act
        opening_fee = self.fetcher.fetch_opening_fee(cast("Any", position))

        # Assert
        assert opening_fee == Decimal("0.582")

    async def test_fetch_all_positions_preserves_small_absolute_collateral_values(self) -> None:
        """Do not reinterpret sub-1 collateral fields as IMR ratios."""
        # Arrange
        self.request_private.return_value = {
            "data": {
                "rows": [
                    {
                        "symbol": "PERP_BTC_USDC",
                        "position_qty": "0.01",
                        "average_open_price": "97000",
                        "mark_price": "97500",
                        "cost_position": "970",
                        "leverage": "10",
                        "collateral": "0.5",
                        "imr": "0.1",
                        "position_id": 11,
                    },
                ],
            },
        }

        # Act
        positions = await self.fetcher.fetch_all_positions()

        # Assert
        assert positions[0]["collateral_stable"] == Decimal("0.5")

    async def test_calculate_close_fee_uses_selected_close_price_not_entry_notional(self) -> None:
        """Estimate close fee from the close notional at the target price."""
        # Arrange
        payloads = _load_payloads()
        self.request_private.return_value = {"data": {"rows": [payloads["position"]]}}

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]
        close_fee = self.fetcher.calculate_close_fee(position, Decimal("120000"))

        # Assert
        assert close_fee == Decimal("0.72")

    async def test_sdk_parity_calculations_preserve_short_position_signs(self) -> None:
        """Keep opening-fee and funding signs correct for short positions."""
        # Arrange
        self.request_private.return_value = {
            "data": {
                "rows": [
                    {
                        "symbol": "PERP_BTC_USDC",
                        "position_id": 88,
                        "position_qty": "-0.01",
                        "average_open_price": "97000",
                        "mark_price": "96500",
                        "cost_position": "-970.582",
                        "leverage": "10",
                        "imr": "0.1",
                        "timestamp": "1710000000000",
                        "last_sum_unitary_funding": "10",
                    },
                ],
            },
        }
        self.request_public.return_value = {
            "data": {
                "rows": [
                    {
                        "symbol": "PERP_BTC_USDC",
                        "sum_unitary_funding": "85",
                    },
                ],
            },
        }

        # Act
        position = (await self.fetcher.fetch_all_positions())[0]

        # Assert
        assert self.fetcher.fetch_opening_fee(position) == Decimal("0.582")
        assert self.fetcher.fetch_funding_fee(position) == Decimal("-0.75")
        assert self.fetcher.calculate_sdk_unsettled_pnl(position, None) == Decimal("5.168")

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
