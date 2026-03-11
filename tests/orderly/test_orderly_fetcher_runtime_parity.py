# ruff: noqa: S101, PLR2004, SLF001

"""Focused parity tests for Orderly fetcher runtime behavior."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
import unittest
from unittest.mock import AsyncMock, Mock, patch

from httpx import HTTPStatusError, Request, Response
import pytest

from plutus_terminal.core.exchange.orderly.fetcher import (
    OrderlyFetcher,
    _extract_retry_after_seconds,
    _history_retry_wait,
)
from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRegistry
from plutus_terminal.core.exchange.orderly.ws_topics import ACCOUNT_TOPICS
from plutus_terminal.core.types_ import PerpsTradeDirection, PerpsTradeType

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient
    from plutus_terminal.core.exchange.orderly.websocket import OrderlyWebsocketManager
    from plutus_terminal.message_bus import MessageBus


def _build_market_registry() -> OrderlyMarketRegistry:
    registry = OrderlyMarketRegistry()
    registry.load_fallback_symbols(("PERP_BTC_USDC",))
    return registry


def _build_message_bus() -> SimpleNamespace:
    return SimpleNamespace(
        balance_fetched=SimpleNamespace(emit=Mock()),
        positions_fetched=SimpleNamespace(emit=Mock()),
        orders_fetched=SimpleNamespace(emit=Mock()),
        subscribed_prices_fetched=SimpleNamespace(emit=Mock()),
    )


def _http_status_error(status_code: int, *, retry_after: str | None = None) -> HTTPStatusError:
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    request = Request("GET", "https://example.invalid/v1/tv/history")
    response = Response(status_code, headers=headers, request=request)
    return HTTPStatusError(f"status {status_code}", request=request, response=response)


def _retry_state(attempt_number: int, exception: BaseException) -> SimpleNamespace:
    return SimpleNamespace(
        attempt_number=attempt_number,
        outcome=SimpleNamespace(exception=lambda: exception),
    )


class OrderlyFetcherRuntimeParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify Orderly fetcher runtime behavior stays deterministic and source-aligned."""

    def setUp(self) -> None:
        """Create deterministic fetcher dependencies for each test."""
        self.request_private = AsyncMock()
        self.request_public = AsyncMock(return_value={"data": {"rows": []}})
        self.rest_client = cast(
            "OrderlyRestClient",
            SimpleNamespace(
                request_private=self.request_private,
                request_public=self.request_public,
                aclose=AsyncMock(),
            ),
        )
        self.websocket_manager = cast(
            "OrderlyWebsocketManager",
            SimpleNamespace(
                ensure_connections=AsyncMock(),
                subscribe_private=AsyncMock(),
                next_private_event=AsyncMock(),
                should_stop=Mock(return_value=False),
                connect_private=AsyncMock(),
                subscribe_public=AsyncMock(),
                unsubscribe_public=AsyncMock(),
                has_public_topics=Mock(return_value=False),
                next_public_event=AsyncMock(),
                stop=AsyncMock(),
            ),
        )
        self.message_bus = _build_message_bus()
        self.fetcher = OrderlyFetcher(
            rest_client=self.rest_client,
            websocket_manager=self.websocket_manager,
            market_registry=_build_market_registry(),
            message_bus=cast("MessageBus", self.message_bus),
        )

    async def test_start_initializes_private_runtime_once_in_expected_order(self) -> None:
        """Connect, subscribe, refresh, and spawn the private consumer exactly once."""
        # Arrange
        call_order: list[str] = []
        consumer_task = cast("asyncio.Task[Any]", Mock())

        async def record_connections() -> None:
            call_order.append("ensure")

        async def record_private_subscribe(topics: tuple[str, ...]) -> None:
            assert topics == ACCOUNT_TOPICS
            call_order.append("subscribe")

        async def record_refresh() -> None:
            call_order.append("refresh")

        async def record_funding_refresh() -> None:
            call_order.append("funding")

        def record_task(coro: Coroutine[object, object, object]) -> object:
            call_order.append("task")
            coro.close()
            return consumer_task

        self.websocket_manager.ensure_connections.side_effect = record_connections
        self.websocket_manager.subscribe_private.side_effect = record_private_subscribe
        self.fetcher._refresh_account_config = AsyncMock(side_effect=record_refresh)  # type: ignore[method-assign]
        self.fetcher._refresh_public_funding_rates = AsyncMock(  # type: ignore[method-assign]
            side_effect=record_funding_refresh,
        )

        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.asyncio.create_task",
            side_effect=record_task,
        ) as create_task_mock:
            # Act
            await self.fetcher.start()
            await self.fetcher.start()

        # Assert
        assert call_order == ["ensure", "subscribe", "refresh", "funding", "task"]
        self.websocket_manager.ensure_connections.assert_awaited_once()
        self.websocket_manager.subscribe_private.assert_awaited_once_with(ACCOUNT_TOPICS)
        self.fetcher._refresh_account_config.assert_awaited_once()  # type: ignore[attr-defined]
        self.fetcher._refresh_public_funding_rates.assert_awaited_once()  # type: ignore[attr-defined]
        create_task_mock.assert_called_once()
        assert self.fetcher._private_consumer_task is consumer_task
        assert self.fetcher._started is True

    async def test_start_keeps_runtime_unstarted_when_private_subscription_fails(self) -> None:
        """Abort startup cleanly when private topic subscription fails."""
        # Arrange
        self.websocket_manager.subscribe_private.side_effect = RuntimeError("subscribe failed")
        self.fetcher._refresh_account_config = AsyncMock()  # type: ignore[method-assign]

        with (
            patch(
                "plutus_terminal.core.exchange.orderly.fetcher.asyncio.create_task",
            ) as create_task_mock,
            pytest.raises(RuntimeError, match="subscribe failed"),
        ):
            # Act / Assert
            await self.fetcher.start()

        self.fetcher._refresh_account_config.assert_not_awaited()  # type: ignore[attr-defined]
        create_task_mock.assert_not_called()
        assert self.fetcher._private_consumer_task is None
        assert self.fetcher._started is False

    async def test_request_chart_history_coalesces_duplicate_inflight_calls_only_while_running(
        self,
    ) -> None:
        """Reuse the same in-flight history task, then issue a fresh request after completion."""
        # Arrange
        release_request = asyncio.Event()
        request_payload = {"data": {"rows": []}}

        async def pending_request(**_: object) -> dict[str, Any]:
            await release_request.wait()
            return request_payload

        self.fetcher._request_chart_history_with_retry = AsyncMock(  # type: ignore[method-assign]
            side_effect=pending_request,
        )
        cache_key = ("PERP_BTC_USDC", "1", 100, 200)

        # Act
        first_request = asyncio.create_task(self.fetcher._request_chart_history(*cache_key))
        await asyncio.sleep(0)
        second_request = asyncio.create_task(self.fetcher._request_chart_history(*cache_key))
        await asyncio.sleep(0)
        assert cache_key in self.fetcher._in_flight_history_requests
        release_request.set()
        first_result, second_result = await asyncio.gather(first_request, second_request)
        third_result = await self.fetcher._request_chart_history(*cache_key)

        # Assert
        assert first_result == request_payload
        assert second_result == request_payload
        assert third_result == request_payload
        assert self.fetcher._request_chart_history_with_retry.await_count == 2  # type: ignore[attr-defined]
        assert cache_key not in self.fetcher._in_flight_history_requests

    async def test_request_chart_history_clears_inflight_entry_after_failures(self) -> None:
        """Drop failed in-flight history requests so later retries are not pinned to stale tasks."""
        # Arrange
        cache_key = ("PERP_BTC_USDC", "1", 100, 200)
        self.fetcher._request_chart_history_with_retry = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("history failed"),
        )

        # Act / Assert
        with pytest.raises(RuntimeError, match="history failed"):
            await self.fetcher._request_chart_history(*cache_key)

        assert cache_key not in self.fetcher._in_flight_history_requests

    def test_extract_retry_after_seconds_returns_numeric_header_values(self) -> None:
        """Use a numeric Retry-After header when Orderly provides one."""
        # Arrange
        error = _http_status_error(429, retry_after="2.75")

        # Act
        retry_after = _extract_retry_after_seconds(error)

        # Assert
        assert retry_after == 2.75

    def test_extract_retry_after_seconds_ignores_invalid_or_non_http_exceptions(self) -> None:
        """Return no retry hint when Retry-After is absent, invalid, or not an HTTP status error."""
        # Arrange
        invalid_header_error = _http_status_error(429, retry_after="later")

        # Act / Assert
        assert _extract_retry_after_seconds(invalid_header_error) is None
        assert _extract_retry_after_seconds(RuntimeError("boom")) is None

    def test_history_retry_wait_prefers_retry_after_header_over_local_backoff(self) -> None:
        """Honor server-provided Retry-After hints for history retries."""
        # Arrange
        retry_state = _retry_state(3, _http_status_error(429, retry_after="7.5"))

        # Act
        retry_wait = _history_retry_wait(retry_state)

        # Assert
        assert retry_wait == 7.5

    def test_history_retry_wait_falls_back_to_source_defined_exponential_delays(self) -> None:
        """Use local backoff rules when Retry-After is missing."""
        # Arrange
        rate_limit_wait = _history_retry_wait(_retry_state(1, _http_status_error(429)))
        server_error_wait = _history_retry_wait(_retry_state(1, _http_status_error(500)))

        # Act / Assert
        assert rate_limit_wait == 1.0
        assert server_error_wait == 0.5

    def test_register_history_rate_limit_sets_shared_cooldown_from_retry_after_header(self) -> None:
        """Track a shared cooldown window after a 429 history response."""
        # Arrange
        error = _http_status_error(429, retry_after="3")

        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic", return_value=100.0
        ):
            # Act
            self.fetcher._register_history_rate_limit(error)

        # Assert
        assert self.fetcher._history_rate_limited_until_monotonic == 103.0

    def test_register_history_rate_limit_ignores_non_429_errors(self) -> None:
        """Leave the shared cooldown untouched for non-rate-limit failures."""
        # Arrange
        error = _http_status_error(500, retry_after="9")

        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic", return_value=100.0
        ):
            # Act
            self.fetcher._register_history_rate_limit(error)

        # Assert
        assert self.fetcher._history_rate_limited_until_monotonic == 0.0

    async def test_apply_balance_event_updates_cached_balance_and_emits_adjusted_total(
        self,
    ) -> None:
        """Update cached balance from private events without blending in unsettled PnL."""
        # Arrange
        self.fetcher._cached_unsettled_pnl = Decimal("2.5")
        event = {
            "topic": "balance",
            "data": {
                "balances": {
                    "USDC": {
                        "holding": "10",
                        "frozen": "1",
                        "pending_short": "2",
                    },
                },
            },
        }

        # Act
        await self.fetcher._apply_balance_event(event)

        # Assert
        assert self.fetcher._cached_stable_balance == Decimal("7")
        self.message_bus.balance_fetched.emit.assert_called_once_with(Decimal("7"))

    async def test_apply_account_event_updates_fee_rate_bps_for_fee_estimates(self) -> None:
        """Use websocket account fee-rate bps for future opening and closing fee estimates."""
        # Arrange
        event = {
            "topic": "account",
            "data": {
                "accountDetail": {
                    "futuresTakerFeeRate": 8,
                },
                "balances": {
                    "USDC": {
                        "holding": "10",
                    },
                },
            },
        }
        position = cast(
            "Any",
            {
                "pair": "Crypto.BTC/USDC",
                "id": 1,
                "position_size_stable": Decimal("970"),
                "collateral_stable": Decimal("97"),
                "open_price": Decimal("97000"),
                "trade_direction": PerpsTradeDirection.LONG,
                "trade_type": PerpsTradeType.MARKET,
                "leverage": Decimal("10"),
                "liquidation_price": Decimal("0"),
                "extra": {},
            },
        )

        # Act
        await self.fetcher._apply_balance_event(event)

        # Assert
        assert self.fetcher.calculate_margin_fee(Decimal("1200")) == Decimal("0.96")
        assert self.fetcher.fetch_opening_fee(position) == Decimal("0.776")
        assert self.fetcher.calculate_close_fee(position, Decimal("120000")) == Decimal("0.96")

    async def test_apply_balance_event_ignores_private_payloads_without_usdc_balance(self) -> None:
        """Do not emit balance updates when the private payload lacks the settlement token."""
        # Arrange
        self.fetcher._cached_stable_balance = Decimal("4")
        event = {
            "topic": "balance",
            "data": {"balances": {"BTC": {"holding": "1"}}},
        }

        # Act
        await self.fetcher._apply_balance_event(event)

        # Assert
        assert self.fetcher._cached_stable_balance == Decimal("4")
        self.message_bus.balance_fetched.emit.assert_not_called()

    async def test_refresh_account_config_uses_bps_from_client_info(self) -> None:
        """Convert REST account fee-rate bps into the fee fraction used for estimates."""
        # Arrange
        self.request_private.return_value = {
            "data": {
                "futures_taker_fee_rate": 8,
            },
        }

        # Act
        await self.fetcher._refresh_account_config()

        # Assert
        assert self.fetcher.calculate_margin_fee(Decimal("1200")) == Decimal("0.96")

    async def test_refresh_balance_throttles_client_info_refresh_with_cache_ttl(self) -> None:
        """Avoid re-fetching `/v1/client/info` on every balance poll within the cache window."""
        # Arrange
        self.fetcher.fetch_stable_balance = AsyncMock(return_value=Decimal("7"))  # type: ignore[method-assign]
        self.request_private.return_value = {
            "data": {
                "futures_taker_fee_rate": 8,
            },
        }

        # Act
        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic",
            return_value=100.0,
        ):
            await self.fetcher._refresh_balance()
        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic",
            return_value=101.0,
        ):
            await self.fetcher._refresh_balance()
        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic",
            return_value=401.0,
        ):
            await self.fetcher._refresh_balance()

        # Assert
        self.fetcher.fetch_stable_balance.assert_awaited()  # type: ignore[attr-defined]
        assert self.request_private.await_count == 2

    async def test_refresh_account_config_honors_429_backoff_before_retrying(self) -> None:
        """Stop hammering `/v1/client/info` after Orderly returns a rate-limit response."""
        # Arrange
        self.request_private.side_effect = _http_status_error(429, retry_after="3")

        # Act
        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic",
            return_value=100.0,
        ):
            await self.fetcher._refresh_account_config()

        self.request_private.side_effect = None
        self.request_private.return_value = {"data": {"futures_taker_fee_rate": 8}}

        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic",
            return_value=102.0,
        ):
            await self.fetcher._refresh_account_config()
        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.time.monotonic",
            return_value=104.0,
        ):
            await self.fetcher._refresh_account_config()

        # Assert
        assert self.fetcher._account_config_rate_limited_until_monotonic == 0.0
        assert self.request_private.await_count == 2

    async def test_apply_positions_event_refreshes_cached_positions_and_balance_messages(
        self,
    ) -> None:
        """Parse private position payloads into cache updates and emit trading balance separately."""
        # Arrange
        self.fetcher._cached_stable_balance = Decimal("10")
        event = {
            "topic": "position",
            "data": {
                "rows": [
                    {
                        "symbol": "PERP_BTC_USDC",
                        "position_qty": "0.01",
                        "cost_position": "970",
                        "imr": "97",
                        "average_open_price": "97000",
                        "mark_price": "97500",
                        "unsettled_pnl": "5",
                        "position_id": 11,
                    },
                ],
            },
        }

        # Act
        await self.fetcher._apply_positions_event(event)

        # Assert
        assert len(self.fetcher._cached_positions) == 1
        assert self.fetcher._cached_positions[0]["id"] == 11
        assert self.fetcher._cached_positions[0]["pair"] == "Crypto.BTC/USDC"
        self.message_bus.positions_fetched.emit.assert_called_once_with(
            self.fetcher._cached_positions
        )
        self.message_bus.balance_fetched.emit.assert_called_once_with(Decimal("10"))

    async def test_apply_positions_event_drops_unknown_or_empty_rows_but_still_emits_snapshot(
        self,
    ) -> None:
        """Emit the current private positions snapshot even when native rows do not map locally."""
        # Arrange
        event = {
            "topic": "position",
            "data": {
                "rows": [
                    {"symbol": "PERP_UNKNOWN_USDC", "position_qty": "1"},
                    {"symbol": "PERP_BTC_USDC", "position_qty": "0"},
                ],
            },
        }

        # Act
        await self.fetcher._apply_positions_event(event)

        # Assert
        assert self.fetcher._cached_positions == []
        self.message_bus.positions_fetched.emit.assert_called_once_with([])
        self.message_bus.balance_fetched.emit.assert_called_once_with(Decimal("0"))

    async def test_apply_positions_event_prefers_free_collateral_for_trading_balance(self) -> None:
        """Use account free collateral as the emitted trading balance when positions payload provides it."""
        # Arrange
        self.fetcher._cached_stable_balance = Decimal("10")
        event = {
            "topic": "position",
            "data": {
                "free_collateral": "8.5",
                "rows": [
                    {
                        "symbol": "PERP_BTC_USDC",
                        "position_qty": "0.01",
                        "cost_position": "970",
                        "imr": "97",
                        "average_open_price": "97000",
                        "mark_price": "97500",
                        "unsettled_pnl": "5",
                        "position_id": 11,
                    },
                ],
            },
        }

        # Act
        await self.fetcher._apply_positions_event(event)

        # Assert
        assert self.fetcher._cached_free_collateral == Decimal("8.5")
        self.message_bus.balance_fetched.emit.assert_called_once_with(Decimal("8.5"))

    async def test_fetch_all_positions_refreshes_public_funding_accumulators_for_sdk_parity(
        self,
    ) -> None:
        """Populate the public funding accumulator cache used by the React SDK formula."""

        # Arrange
        async def request_private(_method: str, path: str, **_kwargs: object) -> dict[str, object]:
            if path == "/v1/positions":
                return {
                    "data": {
                        "rows": [
                            {
                                "symbol": "PERP_BTC_USDC",
                                "position_qty": "0.01",
                                "cost_position": "970",
                                "imr": "0.1",
                                "average_open_price": "97000",
                                "mark_price": "97500",
                                "unsettled_pnl": "5",
                                "position_id": 11,
                                "timestamp": "1710000000000",
                            },
                        ],
                    },
                }

            raise AssertionError(path)

        async def request_public(_method: str, path: str, **_kwargs: object) -> dict[str, object]:
            assert path == "/v1/public/funding_rates"
            return {
                "data": {
                    "rows": [
                        {
                            "symbol": "PERP_BTC_USDC",
                            "sum_unitary_funding": "75.00001234",
                        },
                    ],
                },
            }

        self.rest_client.request_private = AsyncMock(side_effect=request_private)
        self.rest_client.request_public = AsyncMock(side_effect=request_public)
        self.fetcher._rest_client = self.rest_client  # type: ignore[assignment]

        # Act
        await self.fetcher.fetch_all_positions()

        # Assert
        assert self.fetcher._cached_sum_unitary_funding["PERP_BTC_USDC"] == Decimal("75.00001234")

    async def test_receive_subscribed_prices_does_not_overwrite_mark_price_with_bbo_midpoint(
        self,
    ) -> None:
        """Keep positions-table price cache aligned to mark-price events."""
        # Arrange
        events = iter(
            [
                {"topic": "PERP_BTC_USDC@markprice", "data": {"mark_price": "97500"}},
                {"topic": "PERP_BTC_USDC@bbo", "data": {"b": "97000", "a": "98000"}},
            ],
        )
        self.fetcher._started = True
        self.websocket_manager.has_public_topics = Mock(side_effect=[True, True, False])

        async def next_public_event() -> dict[str, object]:
            event = next(events)
            if event["topic"] == "PERP_BTC_USDC@bbo":
                self.fetcher._stop_event.set()
            return event

        self.websocket_manager.next_public_event.side_effect = next_public_event

        # Act
        await self.fetcher.receive_subscribed_prices()

        # Assert
        assert self.fetcher._cached_prices["Crypto.BTC/USDC"]["price"] == Decimal("97500")

    async def test_consume_private_events_refreshes_orders_and_positions_for_execution_topics(
        self,
    ) -> None:
        """Treat private execution events as a signal to refresh both order and position snapshots."""
        # Arrange
        self.fetcher._refresh_orders = AsyncMock()  # type: ignore[method-assign]
        self.fetcher._refresh_positions = AsyncMock()  # type: ignore[method-assign]

        async def next_event() -> dict[str, str]:
            self.fetcher._stop_event.set()
            return {"topic": "executionreport", "data": {}}

        self.websocket_manager.next_private_event.side_effect = next_event

        # Act
        await self.fetcher._consume_private_events()

        # Assert
        self.fetcher._refresh_orders.assert_awaited_once()  # type: ignore[attr-defined]
        self.fetcher._refresh_positions.assert_awaited_once()  # type: ignore[attr-defined]

    async def test_consume_private_events_refreshes_balance_and_positions_for_wallet_topic(
        self,
    ) -> None:
        """Treat wallet updates as a passive signal to refresh trading state."""
        # Arrange
        self.fetcher._refresh_balance = AsyncMock()  # type: ignore[method-assign]
        self.fetcher._refresh_positions = AsyncMock()  # type: ignore[method-assign]

        async def next_event() -> dict[str, str]:
            self.fetcher._stop_event.set()
            return {"topic": "wallet", "data": {}}

        self.websocket_manager.next_private_event.side_effect = next_event

        # Act
        await self.fetcher._consume_private_events()

        # Assert
        self.fetcher._refresh_balance.assert_awaited_once()  # type: ignore[attr-defined]
        self.fetcher._refresh_positions.assert_awaited_once()  # type: ignore[attr-defined]

    async def test_consume_private_events_reconnects_and_replays_account_topics_after_errors(
        self,
    ) -> None:
        """Reconnect the private stream and resubscribe account topics after unexpected errors."""
        # Arrange
        self.websocket_manager.should_stop = Mock(side_effect=[False, True])
        self.websocket_manager.next_private_event.side_effect = RuntimeError("stream dropped")

        with patch(
            "plutus_terminal.core.exchange.orderly.fetcher.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock:
            # Act
            await self.fetcher._consume_private_events()

        # Assert
        sleep_mock.assert_awaited_once_with(0.2)
        self.websocket_manager.connect_private.assert_awaited_once()
        self.websocket_manager.subscribe_private.assert_awaited_once_with(ACCOUNT_TOPICS)
