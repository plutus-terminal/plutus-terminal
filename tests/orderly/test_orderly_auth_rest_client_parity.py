# ruff: noqa: S101, SLF001

"""Focused parity tests for Orderly auth and REST client behavior."""

from __future__ import annotations

from dataclasses import dataclass
import unittest
from unittest.mock import AsyncMock, patch

from plutus_terminal.core.exchange.orderly.auth import (
    build_rest_headers,
    build_rest_signature_payload,
)
from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials
from plutus_terminal.core.exchange.orderly.rest_client import (
    OrderlyRequestError,
    OrderlyRestClient,
    _build_path_with_query,
)


def _build_credentials() -> OrderlyCredentials:
    return OrderlyCredentials(
        account_id="account-id",
        orderly_key="webui-token-key",
        orderly_secret="webui-token-secret",
    )


@dataclass
class _FakeResponse:
    payload: object

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class OrderlyAuthRestClientParityTests(unittest.IsolatedAsyncioTestCase):
    """Verify REST signing and private request shaping stays server-compatible."""

    def setUp(self) -> None:
        """Create a deterministic REST client for each test."""
        self.credentials = _build_credentials()
        self.client = OrderlyRestClient(
            "https://example.invalid",
            credentials=self.credentials,
        )

    async def asyncTearDown(self) -> None:
        """Close the underlying HTTP client after each test."""
        await self.client.aclose()

    def test_build_rest_signature_payload_appends_query_before_serialized_body(self) -> None:
        """Keep the native REST signing preimage order stable."""
        # Arrange
        timestamp_ms = 1_700_000_000_123
        method = "post"
        path_with_query = "/v1/order?symbol=PERP_BTC_USDC"
        serialized_body = '{"symbol":"PERP_BTC_USDC","order_type":"LIMIT"}'

        # Act
        payload = build_rest_signature_payload(
            timestamp_ms,
            method,
            path_with_query,
            serialized_body,
        )

        # Assert
        assert payload == (
            "1700000000123"
            "POST"
            "/v1/order?symbol=PERP_BTC_USDC"
            '{"symbol":"PERP_BTC_USDC","order_type":"LIMIT"}'
        )

    def test_build_rest_headers_sets_required_private_headers_for_json_requests(self) -> None:
        """Include the signed REST headers while preserving WebUI-token credentials."""
        # Arrange
        with patch(
            "plutus_terminal.core.exchange.orderly.auth.sign_orderly_payload",
            return_value="signed-value",
        ) as sign_mock:
            # Act
            headers = build_rest_headers(
                self.credentials,
                "POST",
                "/v1/order?symbol=PERP_BTC_USDC",
                '{"symbol":"PERP_BTC_USDC"}',
                timestamp_ms=1_700_000_000_123,
            )

        # Assert
        sign_mock.assert_called_once_with(
            '1700000000123POST/v1/order?symbol=PERP_BTC_USDC{"symbol":"PERP_BTC_USDC"}',
            "webui-token-secret",
        )
        assert headers == {
            "Content-Type": "application/json",
            "orderly-account-id": "account-id",
            "orderly-key": "webui-token-key",
            "orderly-signature": "signed-value",
            "orderly-timestamp": "1700000000123",
        }

    def test_build_rest_headers_uses_form_content_type_for_get_requests(self) -> None:
        """Keep GET auth headers bodyless and query-signed."""
        # Arrange
        with patch(
            "plutus_terminal.core.exchange.orderly.auth.sign_orderly_payload",
            return_value="signed-value",
        ) as sign_mock:
            # Act
            headers = build_rest_headers(
                self.credentials,
                "GET",
                "/v1/orders?symbol=PERP_BTC_USDC",
                "",
                timestamp_ms=1_700_000_000_123,
            )

        # Assert
        sign_mock.assert_called_once_with(
            "1700000000123GET/v1/orders?symbol=PERP_BTC_USDC",
            "webui-token-secret",
        )
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"

    def test_build_path_with_query_repeats_sequence_values_deterministically(self) -> None:
        """Normalize list-valued query params into a stable signed path."""
        # Arrange
        params = {
            "symbol": "PERP_BTC_USDC",
            "order_id": ["100", "101"],
        }

        # Act
        path_with_query = _build_path_with_query("/v1/orders", params)

        # Assert
        assert path_with_query == "/v1/orders?symbol=PERP_BTC_USDC&order_id=100&order_id=101"

    async def test_request_private_get_signs_query_string_without_serializing_a_body(self) -> None:
        """Forward GET params normally while signing only the canonical query path."""
        # Arrange
        response = _FakeResponse({"success": True, "data": {"rows": []}})
        self.client._client.request = AsyncMock(return_value=response)

        with patch(
            "plutus_terminal.core.exchange.orderly.rest_client.build_rest_headers",
            return_value={"signed": "headers"},
        ) as headers_mock:
            # Act
            payload = await self.client.request_private(
                "GET",
                "/v1/orders",
                params={"symbol": "PERP_BTC_USDC", "page": 2},
            )

        # Assert
        assert payload == {"success": True, "data": {"rows": []}}
        headers_mock.assert_called_once_with(
            self.credentials,
            "GET",
            "/v1/orders?symbol=PERP_BTC_USDC&page=2",
            "",
        )
        self.client._client.request.assert_awaited_once_with(
            "GET",
            "/v1/orders",
            headers={"signed": "headers"},
            params={"symbol": "PERP_BTC_USDC", "page": 2},
        )

    async def test_request_private_post_serializes_json_body_for_signing_and_transport(
        self,
    ) -> None:
        """Serialize private request bodies once and reuse them for signing and content."""
        # Arrange
        response = _FakeResponse({"success": True, "data": {"order_id": "1"}})
        self.client._client.request = AsyncMock(return_value=response)
        json_body = {
            "symbol": "PERP_BTC_USDC",
            "order_type": "LIMIT",
            "order_quantity": "0.01",
        }

        with patch(
            "plutus_terminal.core.exchange.orderly.rest_client.build_rest_headers",
            return_value={"signed": "headers"},
        ) as headers_mock:
            # Act
            payload = await self.client.request_private("POST", "/v1/order", json_body=json_body)

        # Assert
        assert payload == {"success": True, "data": {"order_id": "1"}}
        headers_mock.assert_called_once_with(
            self.credentials,
            "POST",
            "/v1/order",
            '{"symbol":"PERP_BTC_USDC","order_type":"LIMIT","order_quantity":"0.01"}',
        )
        self.client._client.request.assert_awaited_once_with(
            "POST",
            "/v1/order",
            headers={"signed": "headers"},
            content='{"symbol":"PERP_BTC_USDC","order_type":"LIMIT","order_quantity":"0.01"}',
        )

    async def test_request_private_raises_when_credentials_are_missing(self) -> None:
        """Reject private requests before any network call when auth config is absent."""
        # Arrange
        client = OrderlyRestClient("https://example.invalid")
        client._client.request = AsyncMock()

        # Act / Assert
        with self.assertRaisesRegex(OrderlyRequestError, "credentials are required"):
            await client.request_private("GET", "/v1/orders")

        client._client.request.assert_not_awaited()
        await client.aclose()

    async def test_request_private_surfaces_auth_api_failures_as_orderly_request_errors(
        self,
    ) -> None:
        """Keep auth failures on the stable application-error path instead of transport errors."""
        # Arrange
        response = _FakeResponse(
            {"success": False, "code": -1002, "message": "invalid or expired api key"},
        )
        self.client._client.request = AsyncMock(return_value=response)

        with patch(
            "plutus_terminal.core.exchange.orderly.rest_client.build_rest_headers",
            return_value={"signed": "headers"},
        ):
            # Act / Assert
            with self.assertRaisesRegex(
                OrderlyRequestError, r"\[-1002\] invalid or expired api key"
            ):
                await self.client.request_private("GET", "/v1/client/info")

    async def test_request_public_surfaces_generic_application_failures_without_api_code(
        self,
    ) -> None:
        """Raise the generic Orderly application error when the payload omits a numeric code."""
        # Arrange
        response = _FakeResponse({"success": False, "message": "gateway rejected request"})
        self.client._client.request = AsyncMock(return_value=response)

        # Act / Assert
        with self.assertRaisesRegex(OrderlyRequestError, "gateway rejected request"):
            await self.client.request_public("GET", "/v1/public/info")
