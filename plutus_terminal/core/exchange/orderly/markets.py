"""Market metadata and symbol mapping for Orderly."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OrderlyMarketRule:
    """Trading constraints for one Orderly symbol."""

    symbol: str
    pair: str
    base: str
    quote: str
    base_min: Decimal
    base_max: Decimal
    base_tick: Decimal
    quote_min: Decimal
    quote_max: Decimal
    quote_tick: Decimal
    min_notional: Decimal
    max_leverage: int


class OrderlyMarketRegistry:
    """In-memory market metadata fetched dynamically from Orderly API."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._by_symbol: dict[str, OrderlyMarketRule] = {}
        self._symbol_by_pair: dict[str, str] = {}

    @property
    def pairs(self) -> set[str]:
        """Return all formatted terminal pairs available for trading."""
        return set(self._symbol_by_pair)

    def get_rule_by_pair(self, pair: str) -> OrderlyMarketRule:
        """Return rule for one terminal pair."""
        symbol = self._symbol_by_pair[pair]
        return self._by_symbol[symbol]

    def get_rule_by_symbol(self, symbol: str) -> OrderlyMarketRule:
        """Return rule for one orderly symbol."""
        return self._by_symbol[symbol]

    def get_symbol_for_pair(self, pair: str) -> str:
        """Return orderly symbol for terminal pair."""
        return self._symbol_by_pair[pair]

    async def refresh(self, rest_client: OrderlyRestClient) -> None:
        """Refresh registry from `/v1/public/info` response."""
        payload = await rest_client.request_public("GET", "/v1/public/info")
        data = payload.get("data", {})
        rows = data.get("rows", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            rows = []
        by_symbol: dict[str, OrderlyMarketRule] = {}
        symbol_by_pair: dict[str, str] = {}

        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol", ""))
            if not symbol.startswith("PERP_"):
                continue

            try:
                rule = _build_market_rule(row)
            except (InvalidOperation, KeyError, ValueError) as error:
                LOGGER.warning(
                    "Skipping malformed Orderly market row for symbol=%s: %s",
                    symbol or "<missing>",
                    error,
                )
                continue
            by_symbol[rule.symbol] = rule
            symbol_by_pair[rule.pair] = rule.symbol

        if by_symbol:
            self._by_symbol = by_symbol
            self._symbol_by_pair = symbol_by_pair

    def load_fallback_symbols(self, symbols: tuple[str, ...]) -> None:
        """Load conservative fallback symbol rules when bootstrap refresh fails."""
        by_symbol: dict[str, OrderlyMarketRule] = {}
        symbol_by_pair: dict[str, str] = {}
        for symbol in symbols:
            if not symbol.startswith("PERP_"):
                continue
            _, base, quote = symbol.split("_", 2)
            pair = f"Crypto.{base}/{quote}"
            rule = OrderlyMarketRule(
                symbol=symbol,
                pair=pair,
                base=base,
                quote=quote,
                base_min=Decimal("0"),
                base_max=Decimal("999999999"),
                base_tick=Decimal("0.00000001"),
                quote_min=Decimal("0"),
                quote_max=Decimal("999999999"),
                quote_tick=Decimal("0.01"),
                min_notional=Decimal("1"),
                max_leverage=50,
            )
            by_symbol[symbol] = rule
            symbol_by_pair[pair] = symbol

        if by_symbol:
            self._by_symbol = by_symbol
            self._symbol_by_pair = symbol_by_pair


def _to_decimal(value: object, default: str = "0") -> Decimal:
    """Convert value into Decimal with fallback default."""
    raw_value = default if value is None else str(value)
    return Decimal(raw_value)


def _extract_max_leverage(row: dict[str, object]) -> int:
    """Extract max leverage from public symbol row."""
    max_leverage = row.get("max_leverage")
    if isinstance(max_leverage, int):
        return max_leverage
    if isinstance(max_leverage, str) and max_leverage:
        return int(max_leverage)
    return 50


def _build_market_rule(row: dict[str, object]) -> OrderlyMarketRule:
    """Parse one symbol row into normalized market rule."""
    symbol = str(row["symbol"])
    _, base, quote = symbol.split("_", 2)
    pair = f"Crypto.{base}/{quote}"

    return OrderlyMarketRule(
        symbol=symbol,
        pair=pair,
        base=base,
        quote=quote,
        base_min=_to_decimal(row.get("base_min")),
        base_max=_to_decimal(row.get("base_max"), "999999999"),
        base_tick=_to_decimal(row.get("base_tick"), "0.00000001"),
        quote_min=_to_decimal(row.get("quote_min")),
        quote_max=_to_decimal(row.get("quote_max"), "999999999"),
        quote_tick=_to_decimal(row.get("quote_tick"), "0.01"),
        min_notional=_to_decimal(row.get("min_notional"), "1"),
        max_leverage=_extract_max_leverage(row),
    )
