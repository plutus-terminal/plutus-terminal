"""Authentication helpers for Orderly REST and websocket APIs."""

from __future__ import annotations

from base64 import urlsafe_b64encode
import json
import time
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials

_ED25519_PRIVATE_KEY_BYTES = 32

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}


def _decode_base58(value: str) -> bytes:
    """Decode a base58 string into bytes."""
    if not value:
        msg = "Base58 value cannot be empty."
        raise ValueError(msg)

    decimal_value = 0
    for character in value:
        try:
            digit = _BASE58_INDEX[character]
        except KeyError as error:
            msg = "Invalid base58 character in secret."
            raise ValueError(msg) from error
        decimal_value = (decimal_value * 58) + digit

    decoded = b""
    if decimal_value > 0:
        decoded = decimal_value.to_bytes((decimal_value.bit_length() + 7) // 8, byteorder="big")

    leading_zeroes = len(value) - len(value.lstrip("1"))
    return (b"\x00" * leading_zeroes) + decoded


def _decode_orderly_secret(secret: str) -> bytes:
    """Decode Orderly secret into raw ed25519 key bytes."""
    decoded_secret = _decode_base58(secret)
    if len(decoded_secret) != _ED25519_PRIVATE_KEY_BYTES:
        msg = (
            "Orderly secret must decode to "
            f"{_ED25519_PRIVATE_KEY_BYTES} bytes for ed25519 signing."
        )
        raise ValueError(msg)
    return decoded_secret


def serialize_body(body: Mapping[str, Any] | None) -> str:
    """Serialize JSON body for request signing and request payload."""
    if not body:
        return ""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def build_rest_signature_payload(
    timestamp_ms: int,
    method: str,
    path_with_query: str,
    serialized_body: str,
) -> str:
    """Build canonical payload used by Orderly REST signing."""
    return f"{timestamp_ms}{method.upper()}{path_with_query}{serialized_body}"


def sign_orderly_payload(payload: str, orderly_secret: str) -> str:
    """Sign payload with Orderly secret and return URL-safe base64 signature."""
    private_key = Ed25519PrivateKey.from_private_bytes(_decode_orderly_secret(orderly_secret))
    signature = private_key.sign(payload.encode("utf-8"))
    return urlsafe_b64encode(signature).decode("utf-8")


def build_rest_headers(
    credentials: OrderlyCredentials,
    method: str,
    path_with_query: str,
    serialized_body: str,
    *,
    timestamp_ms: int | None = None,
) -> dict[str, str]:
    """Build required headers for private Orderly REST endpoints."""
    timestamp = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    payload = build_rest_signature_payload(timestamp, method, path_with_query, serialized_body)
    signature = sign_orderly_payload(payload, credentials.orderly_secret)
    content_type = "application/x-www-form-urlencoded"
    if method.upper() not in {"GET", "DELETE"}:
        content_type = "application/json"

    return {
        "Content-Type": content_type,
        "orderly-account-id": credentials.account_id,
        "orderly-key": credentials.orderly_key,
        "orderly-signature": signature,
        "orderly-timestamp": str(timestamp),
    }


def build_ws_auth_payload(
    credentials: OrderlyCredentials,
    *,
    timestamp_ms: int | None = None,
) -> dict[str, str | int]:
    """Build auth payload for Orderly private websocket authentication."""
    timestamp = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    signature = sign_orderly_payload(str(timestamp), credentials.orderly_secret)
    return {
        "orderly_key": credentials.orderly_key,
        "timestamp": timestamp,
        "sign": signature,
    }
