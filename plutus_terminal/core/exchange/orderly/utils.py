"""Orderly Exchange utils."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import TypedDict
import urllib.parse

import base58
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

LOGGER = logging.getLogger(__name__)

# Constants
ORDERLY_MAINNET_API_URL = "https://api-evm.orderly.org"
ORDERLY_TESTNET_API_URL = "https://testnet-api-evm.orderly.org"

ORDERLY_MAINNET_WS_URL = "wss://ws-evm.orderly.org/ws/stream"
ORDERLY_TESTNET_WS_URL = "wss://testnet-ws-evm.orderly.org/ws/stream"

ORDERLY_MAINNET_PRIVATE_WS_URL = "wss://ws-private-evm.orderly.org/v2/ws/private/stream"
ORDERLY_TESTNET_PRIVATE_WS_URL = (
    "wss://testnet-ws-private-evm.orderly.org/v2/ws/private/stream"
)


class OrderlySigner:
    """Signer for Orderly Network."""

    def __init__(self, account_id: str, key_pair: str) -> None:
        """Initialize signer.

        Args:
            account_id (str): Orderly Account ID.
            key_pair (str): Base58 encoded private key.
        """
        self.account_id = account_id
        # Decode base58 private key
        try:
            decoded_key = base58.b58decode(key_pair)
            self.private_key = Ed25519PrivateKey.from_private_bytes(decoded_key)
        except Exception:
            LOGGER.exception("Failed to decode private key.")
            raise

    def generate_signature(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        timestamp: int | None = None,
    ) -> str:
        """Generate signature for Orderly API request.

        Args:
            method (str): HTTP method (GET, POST, etc).
            path (str): Request path (e.g. /v1/orders).
            params (dict, optional): Request body or query params.
            timestamp (int, optional): Timestamp in milliseconds.

        Returns:
            str: Base64 encoded signature.
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        # 1. Normalize request content
        # <timestamp><method><path><body_string>
        message = f"{timestamp}{method.upper()}{path}"

        if params:
            if method.upper() in ["GET", "DELETE"]:
                # Append query params to message if not already in path
                # Assuming path does not have query params yet if params dict is provided separately.
                # However, if path already has query params, we shouldn't duplicate?
                # The caller should pass params=None if params are already in path.
                # If params are passed as dict, we append them sorted?
                # Orderly docs say: "Append path of request including query parameters (without base URL)"

                # Check if path has query params
                if "?" not in path:
                    # Append params as query string
                    # Orderly might require sorted keys?
                    # The docs example: /v1/orders?symbol=PERP_BTC_USDC
                    # It doesn't specify sorting but usually it's standard.
                    query_string = urllib.parse.urlencode(params)
                    message += f"?{query_string}"
                else:
                    # Path already has query params, assume they are correct.
                    # But if params dict is also passed, it's ambiguous.
                    # We assume if params is passed, it's not in path.
                    pass
            else:
                # Only POST/PUT bodies are appended as JSON string.
                message += json.dumps(params, separators=(",", ":"))

        # 2. Sign
        signature_bytes = self.private_key.sign(message.encode("utf-8"))

        # 3. Encode base64 url-safe
        return (
            base64.urlsafe_b64encode(signature_bytes).decode("utf-8").rstrip("=")
        )

    def get_headers(
        self,
        method: str,
        path: str,
        params: dict | None = None,
    ) -> dict[str, str]:
        """Get headers for Orderly API request.

        Args:
            method (str): HTTP method.
            path (str): Request path.
            params (dict, optional): Request params/body.

        Returns:
            dict: Headers.
        """
        timestamp = int(time.time() * 1000)

        # If method is GET/DELETE, we need to pass the full path with params to generate_signature
        # because the signature depends on it.
        # But `generate_signature` logic above appends params if passed.
        # We need to ensure that `httpx` request also uses the same params/url.

        # The `trader.py` passes `params` to `_send_request`, which passes them to `get_headers` AND `httpx`.
        # `httpx` handles param encoding.
        # But `generate_signature` needs to match `httpx` encoding.
        # `httpx` encoding is standard.

        # NOTE: `trader.py` calls `httpx.delete(url, headers=headers, params=params)`.
        # `url` there is `base_url + path`.
        # So `httpx` will append `?param=...` to URL.
        # `generate_signature` should simulate this.

        signature = self.generate_signature(method, path, params, timestamp)

        # Get public key in format 'ed25519:<base58_encoded_public_key>'
        public_key_bytes = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        public_key_b58 = base58.b58encode(public_key_bytes).decode("utf-8")
        orderly_key = f"ed25519:{public_key_b58}"

        return {
            "Content-Type": "application/json"
            if method.upper() != "GET"
            else "application/x-www-form-urlencoded",
            "orderly-account-id": self.account_id,
            "orderly-key": orderly_key,
            "orderly-signature": signature,
            "orderly-timestamp": str(timestamp),
        }


class OpenTradingArgs(TypedDict):
    """Trading Arguments."""

    symbol: str
    order_type: str
    order_price: float | None
    order_quantity: float
    side: str
    reduce_only: bool
    visible_quantity: float  # Optional, 0 for hidden
