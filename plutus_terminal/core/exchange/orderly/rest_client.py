"""REST client for Orderly exchange APIs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from httpx import AsyncClient, HTTPStatusError

from plutus_terminal.core.exchange.orderly.auth import build_rest_headers, serialize_body

if TYPE_CHECKING:
    from collections.abc import Mapping

    from plutus_terminal.core.exchange.orderly.models import OrderlyCredentials

LOGGER = logging.getLogger(__name__)
_HTTP_TOO_MANY_REQUESTS = 429


class OrderlyRequestError(Exception):
    """Raised when Orderly returns an application-level error."""

    @classmethod
    def from_api_error(cls, code: int, message: str) -> OrderlyRequestError:
        """Create exception from Orderly API code and message."""
        error_message = f"[{code}] {message}"
        return cls(error_message)


class OrderlyRestClient:
    """HTTP client for Orderly public and private REST endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        credentials: OrderlyCredentials | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        """Initialize client with base URL and optional credentials."""
        self._credentials = credentials
        self._client = AsyncClient(base_url=base_url, timeout=timeout_seconds)

    async def aclose(self) -> None:
        """Close underlying HTTP resources."""
        await self._client.aclose()

    async def request_public(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a public endpoint."""
        return await self._request(method=method, path=path, params=params)

    async def request_private(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a private endpoint using Orderly auth headers."""
        if self._credentials is None:
            msg = "Orderly credentials are required for private requests."
            raise OrderlyRequestError(msg)
        return await self._request(
            method=method,
            path=path,
            params=params,
            json_body=json_body,
            credentials=self._credentials,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        credentials: OrderlyCredentials | None = None,
    ) -> dict[str, Any]:
        request_method = method.upper()
        path_with_query = _build_path_with_query(path, params)
        serialized_body = ""
        headers: dict[str, str] = {}
        if credentials is not None:
            if request_method not in {"GET", "DELETE"}:
                serialized_body = serialize_body(json_body)
            headers = build_rest_headers(
                credentials,
                request_method,
                path_with_query,
                serialized_body,
            )

        kwargs: dict[str, Any] = {"headers": headers}
        if request_method in {"GET", "DELETE"}:
            kwargs["params"] = params
        elif json_body is not None:
            kwargs["content"] = serialized_body

        try:
            response = await self._client.request(request_method, path, **kwargs)
            response.raise_for_status()
        except HTTPStatusError as error:
            if error.response.status_code == _HTTP_TOO_MANY_REQUESTS:
                LOGGER.warning(
                    "Orderly rate-limited request: %s %s",
                    request_method,
                    path,
                )
            else:
                LOGGER.exception("Orderly HTTP request failed: %s %s", request_method, path)
            raise

        payload = response.json()
        if isinstance(payload, dict):
            _raise_for_orderly_error(payload)
            return payload

        msg = "Unexpected non-object response from Orderly API."
        raise OrderlyRequestError(msg)


def _build_path_with_query(path: str, params: Mapping[str, Any] | None) -> str:
    """Build canonical path string including query params for signing."""
    if not params:
        return path
    query = urlencode(list(params.items()), doseq=True)
    return f"{path}?{query}"


def _raise_for_orderly_error(payload: dict[str, Any]) -> None:
    """Raise when Orderly response indicates an error."""
    success = payload.get("success")
    if success is False:
        code = payload.get("code")
        message = payload.get("message", "Unknown Orderly API error")
        if code is None:
            raise OrderlyRequestError(str(message))
        raise OrderlyRequestError.from_api_error(int(code), str(message))
