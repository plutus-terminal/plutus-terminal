"""Models for Orderly exchange integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypedDict


class OrderlyNetwork(StrEnum):
    """Supported Orderly environments."""

    MAINNET = "mainnet"
    TESTNET = "testnet"


@dataclass(frozen=True, slots=True)
class OrderlyCredentials:
    """Credentials used for Orderly private endpoints."""

    account_id: str
    orderly_key: str
    orderly_secret: str


@dataclass(frozen=True, slots=True)
class OrderlyEndpoints:
    """Orderly REST and websocket base URLs."""

    rest_url: str
    public_ws_url: str
    private_ws_url: str


def endpoints_for_network(network: OrderlyNetwork) -> OrderlyEndpoints:
    """Return endpoint URLs for the selected network."""
    if network is OrderlyNetwork.TESTNET:
        return OrderlyEndpoints(
            rest_url="https://testnet-api.orderly.org",
            public_ws_url="wss://testnet-ws-evm.orderly.org/ws/stream",
            private_ws_url="wss://testnet-ws-private-evm.orderly.org/v2/ws/private/stream",
        )

    return OrderlyEndpoints(
        rest_url="https://api.orderly.org",
        public_ws_url="wss://ws-evm.orderly.org/ws/stream",
        private_ws_url="wss://ws-private-evm.orderly.org/v2/ws/private/stream",
    )


class OrderlyApiErrorBody(TypedDict, total=False):
    """Error body shape returned by Orderly API."""

    code: int
    message: str
    success: bool
    data: Any
