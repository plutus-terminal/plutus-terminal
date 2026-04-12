# ruff: noqa: S101, PLR2004

"""Focused parity tests for Orderly market metadata and constraints behavior."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
import unittest
from unittest.mock import AsyncMock

import pytest

from plutus_terminal.core.exceptions import InvalidOrderSizeError
from plutus_terminal.core.exchange.orderly.constraints import (
    quantize_base_size,
    quantize_price,
    validate_order_size,
)
from plutus_terminal.core.exchange.orderly.markets import (
    OrderlyMarketRegistry,
    OrderlyMarketRule,
)

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient


def _build_market_rule(**overrides: object) -> OrderlyMarketRule:
    market_rule = OrderlyMarketRule(
        symbol="PERP_BTC_USDC",
        pair="Crypto.BTC/USDC",
        base="BTC",
        quote="USDC",
        base_min=Decimal("0.001"),
        base_max=Decimal(100),
        base_tick=Decimal("0.001"),
        quote_min=Decimal(1),
        quote_max=Decimal(1000000),
        quote_tick=Decimal("0.10"),
        min_notional=Decimal(10),
        max_leverage=25,
    )
    return replace(market_rule, **overrides)


class OrderlyMarketRegistryParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify registry refresh behavior matches current Orderly metadata parsing."""

    async def test_refresh_parses_perp_rows_into_dynamic_market_rules(self) -> None:
        """Load only PERP rows and normalize pair/rule fields from public info."""
        # Arrange
        request_public = AsyncMock(
            return_value={
                "data": {
                    "rows": [
                        {
                            "symbol": "PERP_BTC_USDC",
                            "base_min": "0.001",
                            "base_max": "250",
                            "base_tick": "0.001",
                            "quote_min": "1",
                            "quote_max": "1000000",
                            "quote_tick": "0.10",
                            "min_notional": "5",
                            "max_leverage": "40",
                        },
                        {
                            "symbol": "SPOT_ETH_USDC",
                            "base_min": "0.01",
                        },
                        "not-a-row",
                    ],
                },
            },
        )
        registry = OrderlyMarketRegistry()

        # Act
        await registry.refresh(
            cast("OrderlyRestClient", SimpleNamespace(request_public=request_public)),
        )

        # Assert
        request_public.assert_awaited_once_with("GET", "/v1/public/info")
        assert registry.pairs == {"Crypto.BTC/USDC"}
        assert registry.get_symbol_for_pair("Crypto.BTC/USDC") == "PERP_BTC_USDC"
        rule = registry.get_rule_by_symbol("PERP_BTC_USDC")
        assert rule == OrderlyMarketRule(
            symbol="PERP_BTC_USDC",
            pair="Crypto.BTC/USDC",
            base="BTC",
            quote="USDC",
            base_min=Decimal("0.001"),
            base_max=Decimal(250),
            base_tick=Decimal("0.001"),
            quote_min=Decimal(1),
            quote_max=Decimal(1000000),
            quote_tick=Decimal("0.10"),
            min_notional=Decimal(5),
            max_leverage=40,
        )

    async def test_refresh_replaces_fallback_rules_with_latest_server_metadata(self) -> None:
        """Prefer refreshed server constraints over conservative fallback defaults."""
        # Arrange
        request_public = AsyncMock(
            return_value={
                "data": {
                    "rows": [
                        {
                            "symbol": "PERP_BTC_USDC",
                            "base_min": "0.01",
                            "base_max": "10",
                            "base_tick": "0.01",
                            "quote_min": "10",
                            "quote_max": "500000",
                            "quote_tick": "0.50",
                            "min_notional": "25",
                            "max_leverage": 12,
                        },
                    ],
                },
            },
        )
        registry = OrderlyMarketRegistry()
        registry.load_fallback_symbols(("PERP_BTC_USDC",))

        # Act
        await registry.refresh(
            cast("OrderlyRestClient", SimpleNamespace(request_public=request_public)),
        )

        # Assert
        refreshed_rule = registry.get_rule_by_pair("Crypto.BTC/USDC")
        assert refreshed_rule.base_min == Decimal("0.01")
        assert refreshed_rule.base_tick == Decimal("0.01")
        assert refreshed_rule.quote_tick == Decimal("0.50")
        assert refreshed_rule.min_notional == Decimal(25)
        assert refreshed_rule.max_leverage == 12

    async def test_refresh_skips_malformed_rows_and_keeps_valid_perp_rows(self) -> None:
        """Ignore malformed PERP rows instead of aborting the whole refresh."""
        # Arrange
        request_public = AsyncMock(
            return_value={
                "data": {
                    "rows": [
                        {
                            "symbol": "PERP_BTC_USDC",
                            "base_min": "bad-decimal",
                        },
                        {
                            "symbol": "PERP_ETH_USDC",
                            "base_min": "0.01",
                            "base_max": "100",
                            "base_tick": "0.01",
                            "quote_min": "1",
                            "quote_max": "1000000",
                            "quote_tick": "0.10",
                            "min_notional": "5",
                            "max_leverage": "20",
                        },
                    ],
                },
            },
        )
        registry = OrderlyMarketRegistry()

        # Act
        await registry.refresh(
            cast("OrderlyRestClient", SimpleNamespace(request_public=request_public)),
        )

        # Assert
        assert registry.pairs == {"Crypto.ETH/USDC"}
        assert registry.get_symbol_for_pair("Crypto.ETH/USDC") == "PERP_ETH_USDC"

    async def test_refresh_preserves_existing_rules_when_payload_has_no_valid_rows(self) -> None:
        """Keep the previous registry when bootstrap data is entirely malformed."""
        # Arrange
        request_public = AsyncMock(return_value={"data": {"rows": [{"symbol": "PERP_BTC_USDC"}]}})
        registry = OrderlyMarketRegistry()
        registry.load_fallback_symbols(("PERP_BTC_USDC",))

        # Act
        await registry.refresh(
            cast("OrderlyRestClient", SimpleNamespace(request_public=request_public)),
        )

        # Assert
        assert registry.pairs == {"Crypto.BTC/USDC"}
        assert registry.get_symbol_for_pair("Crypto.BTC/USDC") == "PERP_BTC_USDC"

    async def test_load_fallback_symbols_ignores_non_perp_inputs(self) -> None:
        """Skip fallback entries that are not perpetual symbols."""
        # Arrange
        registry = OrderlyMarketRegistry()

        # Act
        registry.load_fallback_symbols(("SPOT_BTC_USDC",))

        # Assert
        assert registry.pairs == set()


class OrderlyConstraintsParityTests(unittest.TestCase):
    """Verify current constraint behavior from dynamic market metadata."""

    def test_quantize_price_and_base_size_round_down_to_market_ticks(self) -> None:
        """Round price and base size down to server-provided tick sizes."""
        # Arrange
        market_rule = _build_market_rule(
            base_tick=Decimal("0.005"),
            quote_tick=Decimal("0.25"),
        )

        # Act
        quantized_price = quantize_price(Decimal("97500.74"), market_rule)
        quantized_size = quantize_base_size(Decimal("0.0199"), market_rule)

        # Assert
        assert quantized_price == Decimal("97500.50")
        assert quantized_size == Decimal("0.015")

    def test_quantize_helpers_raise_when_tick_is_not_positive(self) -> None:
        """Fail fast when market metadata exposes a non-positive tick size."""
        # Arrange
        market_rule = _build_market_rule(base_tick=Decimal(0), quote_tick=Decimal(0))

        # Act / Assert
        with pytest.raises(ValueError, match="step=0"):
            quantize_price(Decimal("97500.74"), market_rule)

        with pytest.raises(ValueError, match="step=0"):
            quantize_base_size(Decimal("0.0199"), market_rule)

    def test_validate_order_size_accepts_values_at_dynamic_minimum_boundaries(self) -> None:
        """Accept orders that meet current base-size and min-notional rules exactly."""
        # Arrange
        market_rule = _build_market_rule(
            base_min=Decimal("0.01"),
            base_max=Decimal(10),
            min_notional=Decimal(25),
        )

        # Act
        result = validate_order_size(
            base_size=Decimal("0.01"),
            limit_price=Decimal(2500),
            market_rule=market_rule,
        )

        # Assert
        assert result is None

    def test_validate_order_size_rejects_zero_and_base_size_below_minimum(self) -> None:
        """Reject non-positive or too-small quantities before submitting orders."""
        # Arrange
        market_rule = _build_market_rule(base_min=Decimal("0.01"))

        # Act / Assert
        with pytest.raises(InvalidOrderSizeError, match="greater than zero"):
            validate_order_size(
                base_size=Decimal(0),
                limit_price=Decimal(1000),
                market_rule=market_rule,
            )

        with pytest.raises(InvalidOrderSizeError, match=r"Minimum is 0\.01"):
            validate_order_size(
                base_size=Decimal("0.009"),
                limit_price=Decimal(1000),
                market_rule=market_rule,
            )

    def test_validate_order_size_rejects_base_size_above_maximum(self) -> None:
        """Reject sizes that exceed the dynamic base-size ceiling."""
        # Arrange
        market_rule = _build_market_rule(base_max=Decimal(2))

        # Act / Assert
        with pytest.raises(InvalidOrderSizeError, match="Maximum is 2"):
            validate_order_size(
                base_size=Decimal("2.001"),
                limit_price=Decimal(1000),
                market_rule=market_rule,
            )

    def test_validate_order_size_rejects_notional_below_minimum(self) -> None:
        """Reject orders whose dynamic notional is below the market minimum."""
        # Arrange
        market_rule = _build_market_rule(min_notional=Decimal(50))

        # Act / Assert
        with pytest.raises(InvalidOrderSizeError, match="Minimum is 50"):
            validate_order_size(
                base_size=Decimal("0.01"),
                limit_price=Decimal(4000),
                market_rule=market_rule,
            )

    def test_validate_order_size_does_not_enforce_quote_or_mark_price_range_rules_yet(self) -> None:
        """Document the current gap: size validation ignores quote bounds and mark-price range."""
        # Arrange
        market_rule = _build_market_rule(
            quote_min=Decimal(100),
            quote_max=Decimal(110),
            min_notional=Decimal(1),
        )

        # Act
        result = validate_order_size(
            base_size=Decimal(1),
            limit_price=Decimal(1000),
            market_rule=market_rule,
        )

        # Assert
        assert result is None
