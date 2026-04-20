"""Deferred TP/SL coordination for Orderly entry orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import time
from typing import TYPE_CHECKING

from plutus_terminal.core.exchange.types import PerpsTradeType

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.types import OrderData, PerpsPosition
    from plutus_terminal.core.types_ import PerpsTradeDirection


_MARKET_INTENT_TTL_MS = 60_000
_LIMIT_INTENT_TTL_MS = 30 * 60_000


@dataclass(slots=True)
class PositionSnapshot:
    """Lightweight position snapshot used for safe TP/SL matching."""

    position_size_stable: Decimal
    base_size: Decimal | None
    timestamp_ms: int | None


@dataclass(slots=True)
class PendingTpSlIntent:
    """Store deferred TP/SL protection intent until a position is live."""

    pair: str
    symbol: str
    trade_direction: PerpsTradeDirection
    trade_type: PerpsTradeType
    take_profit_price: Decimal | None
    stop_loss_price: Decimal | None
    reference_price: Decimal
    created_at_ms: int
    expires_at_ms: int
    source_order_id: str | None
    original_position: PositionSnapshot | None
    attempts: int = 0
    intent_id: str = field(init=False)

    def __post_init__(self) -> None:
        """Build deterministic-ish in-memory intent id."""
        self.intent_id = (
            f"{self.symbol}:{self.trade_direction.name}:{self.trade_type.name}:{self.created_at_ms}"
        )


class OrderlyTpSlCoordinator:
    """Track deferred TP/SL intents until matching positions appear."""

    def __init__(self) -> None:
        """Initialize in-memory coordinator state."""
        self._pending_intents: list[PendingTpSlIntent] = []

    def create_intent(
        self,
        *,
        pair: str,
        symbol: str,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        take_profit_price: Decimal | None,
        stop_loss_price: Decimal | None,
        reference_price: Decimal,
        source_order_id: str | None,
        original_position: PositionSnapshot | None,
    ) -> PendingTpSlIntent:
        """Create one pending TP/SL intent for a regular entry order."""
        created_at_ms = _now_ms()
        ttl_ms = (
            _MARKET_INTENT_TTL_MS if trade_type is PerpsTradeType.MARKET else _LIMIT_INTENT_TTL_MS
        )
        return PendingTpSlIntent(
            pair=pair,
            symbol=symbol,
            trade_direction=trade_direction,
            trade_type=trade_type,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            reference_price=reference_price,
            created_at_ms=created_at_ms,
            expires_at_ms=created_at_ms + ttl_ms,
            source_order_id=source_order_id,
            original_position=original_position,
        )

    def enqueue(self, intent: PendingTpSlIntent) -> None:
        """Store one deferred TP/SL intent."""
        self._pending_intents.append(intent)

    def pending_intents(self) -> tuple[PendingTpSlIntent, ...]:
        """Return current pending intents for inspection."""
        return tuple(self._pending_intents)

    def pop_ready_intents(
        self,
        *,
        positions: list[PerpsPosition],
    ) -> list[tuple[PendingTpSlIntent, PerpsPosition]]:
        """Remove and return intents whose matching position is now live."""
        ready: list[tuple[PendingTpSlIntent, PerpsPosition]] = []
        remaining: list[PendingTpSlIntent] = []
        for intent in self._pending_intents:
            matched_position = _find_matching_position(intent, positions)
            if matched_position is None:
                remaining.append(intent)
                continue
            intent.attempts += 1
            ready.append((intent, matched_position))
        self._pending_intents = remaining
        return ready

    def pop_expired_intents(self) -> list[PendingTpSlIntent]:
        """Remove and return intents whose retry window elapsed."""
        now_ms = _now_ms()
        expired: list[PendingTpSlIntent] = []
        remaining: list[PendingTpSlIntent] = []
        for intent in self._pending_intents:
            if intent.expires_at_ms <= now_ms:
                expired.append(intent)
            else:
                remaining.append(intent)
        self._pending_intents = remaining
        return expired

    def pop_abandoned_limit_intents(
        self,
        *,
        open_orders: list[OrderData],
    ) -> list[PendingTpSlIntent]:
        """Drop limit intents whose parent order is no longer open."""
        remaining: list[PendingTpSlIntent] = []
        abandoned: list[PendingTpSlIntent] = []
        for intent in self._pending_intents:
            if intent.trade_type is PerpsTradeType.MARKET:
                remaining.append(intent)
                continue
            if intent.source_order_id is None or _has_open_parent_order(intent, open_orders):
                remaining.append(intent)
                continue
            abandoned.append(intent)
        self._pending_intents = remaining
        return abandoned


def _find_matching_position(
    intent: PendingTpSlIntent,
    positions: list[PerpsPosition],
) -> PerpsPosition | None:
    """Return matching live position only after a meaningful state change."""
    for position in positions:
        if (
            position["pair"] != intent.pair
            or position["trade_direction"] is not intent.trade_direction
        ):
            continue
        current_snapshot = snapshot_from_position(position)
        if current_snapshot.position_size_stable <= Decimal(0):
            continue
        if _position_changed_since_snapshot(
            intent.original_position, current_snapshot, intent.created_at_ms
        ):
            return position
    return None


def snapshot_from_position(position: PerpsPosition) -> PositionSnapshot:
    """Build comparable snapshot from one parsed position payload."""
    position_extra = position.get("extra", {})
    base_size = None
    timestamp_ms = None
    if isinstance(position_extra, dict):
        base_size = _optional_decimal(position_extra.get("base_size"))
        timestamp_ms = _optional_int(position_extra.get("timestamp"))
    return PositionSnapshot(
        position_size_stable=position["position_size_stable"],
        base_size=base_size,
        timestamp_ms=timestamp_ms,
    )


def _position_changed_since_snapshot(
    original: PositionSnapshot | None,
    current: PositionSnapshot,
    created_at_ms: int,
) -> bool:
    """Return whether current position plausibly reflects the submitted entry."""
    if original is None:
        return True
    if current.position_size_stable != original.position_size_stable:
        return True
    if current.base_size != original.base_size:
        return True
    if current.timestamp_ms is None or original.timestamp_ms is None:
        return False
    return current.timestamp_ms > max(original.timestamp_ms, created_at_ms)


def _has_open_parent_order(intent: PendingTpSlIntent, open_orders: list[OrderData]) -> bool:
    """Return whether the parent regular order still exists in open orders cache."""
    source_order_id = intent.source_order_id
    if source_order_id is None:
        return False
    for order in open_orders:
        if not order["order_type"].is_regular_order:
            continue
        if order["pair"] != intent.pair or order["trade_direction"] is not intent.trade_direction:
            continue
        order_extra = order.get("extra", {})
        native_order_id = None
        if isinstance(order_extra, dict):
            native_order_id = order_extra.get("native_order_id")
        if str(order["id"]) == source_order_id or str(native_order_id) == source_order_id:
            return True
    return False


def _optional_decimal(value: object | None) -> Decimal | None:
    """Return Decimal for present numeric values."""
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _optional_int(value: object | None) -> int | None:
    """Return int for present numeric values."""
    if value in (None, ""):
        return None
    return int(str(value))


def _now_ms() -> int:
    """Return current wall-clock timestamp in milliseconds."""
    return int(time.time() * 1000)
