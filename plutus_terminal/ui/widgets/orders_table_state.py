"""State helpers for the orders table."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.types import OrderData

OrderRowKey = tuple[str, str]


def get_order_row_key(order: OrderData) -> OrderRowKey:
    """Build a stable row key for an order."""
    return (order["pair"], get_order_identity_key(order))


def get_order_identity_key(order: OrderData) -> str:
    """Build a collision-resistant identity key for one order."""
    order_extra = order.get("extra", {})
    if not isinstance(order_extra, dict):
        order_extra = {}

    identity_parts = [
        str(order["id"]),
        _extra_text(order_extra, "native_order_id"),
        _extra_text(order_extra, "client_order_id"),
        _extra_text(order_extra, "algo_order_id"),
        _extra_text(order_extra, "root_algo_order_id"),
        str(order["order_type"].value),
        str(order["trade_direction"].value),
        _decimal_text(order["trigger_price"]),
        _decimal_text(order["size_stable"]),
        str(order["reduce_only"]),
    ]
    return "|".join(identity_parts)


def _extra_text(order_extra: dict[str, Any], key: str) -> str:
    """Return normalized string value from order extras."""
    value = order_extra.get(key, "")
    return str(value).strip()


def _decimal_text(value: object) -> str:
    """Return a stable decimal string for UI identity keys."""
    return format(value, "f")


def get_changed_plain_fields(previous_order: OrderData, next_order: OrderData) -> set[str]:
    """Return plain fields that changed between two orders."""
    changed_fields: set[str] = set()
    if previous_order["pair"] != next_order["pair"]:
        changed_fields.add("pair")
    if previous_order["trade_direction"] != next_order["trade_direction"]:
        changed_fields.add("trade_direction")
    if previous_order["order_type"] != next_order["order_type"]:
        changed_fields.add("order_kind")
        changed_fields.add("order_type")
    if previous_order["size_stable"] != next_order["size_stable"]:
        changed_fields.add("size_stable")
    if previous_order["reduce_only"] != next_order["reduce_only"]:
        changed_fields.add("reduce_only")
    if previous_order["trigger_price"] != next_order["trigger_price"]:
        changed_fields.add("trigger_price")
    if previous_order.get("extra") != next_order.get("extra"):
        changed_fields.update({"order_kind", "order_type", "trigger_price"})
    return changed_fields


def get_row_keys(orders: list[OrderData]) -> list[OrderRowKey]:
    """Return row keys for the provided orders."""
    return [get_order_row_key(order) for order in orders]


def build_row_lookup(orders: list[OrderData]) -> dict[OrderRowKey, int]:
    """Build a row lookup keyed by order identity."""
    return {get_order_row_key(order): index for index, order in enumerate(orders)}
