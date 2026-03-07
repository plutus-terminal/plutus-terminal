"""State helpers for the positions table."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.types import PerpsPosition

PositionRowKey = tuple[int, str, bool]

PLAIN_POSITION_FIELDS = (
    "pair",
    "trade_direction",
    "collateral_stable",
    "leverage",
    "position_size_stable",
    "open_price",
)


def get_position_row_key(position: PerpsPosition) -> PositionRowKey:
    """Build a stable row key for a position."""
    return (position["id"], position["pair"], position["trade_direction"].value)


def get_changed_plain_fields(
    previous_position: PerpsPosition,
    next_position: PerpsPosition,
) -> set[str]:
    """Return plain fields that changed between two positions."""
    changed_fields: set[str] = set()
    if previous_position["pair"] != next_position["pair"]:
        changed_fields.add("pair")
    if previous_position["trade_direction"] != next_position["trade_direction"]:
        changed_fields.add("trade_direction")
    if previous_position["collateral_stable"] != next_position["collateral_stable"]:
        changed_fields.add("collateral_stable")
    if previous_position["leverage"] != next_position["leverage"]:
        changed_fields.add("leverage")
    if previous_position["position_size_stable"] != next_position["position_size_stable"]:
        changed_fields.add("position_size_stable")
    if previous_position["open_price"] != next_position["open_price"]:
        changed_fields.add("open_price")
    return changed_fields


def get_row_keys(positions: list[PerpsPosition]) -> list[PositionRowKey]:
    """Return row keys for the provided positions."""
    return [get_position_row_key(position) for position in positions]


def build_row_lookup(positions: list[PerpsPosition]) -> dict[PositionRowKey, int]:
    """Build a row lookup keyed by position identity."""
    return {get_position_row_key(position): index for index, position in enumerate(positions)}
