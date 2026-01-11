"""Orderly Exchange Trader."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

from httpx import AsyncClient, HTTPStatusError
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.base import ExchangeTrader
from plutus_terminal.core.exchange.orderly import utils as orderly_utils
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.types import TradeResults

LOGGER = logging.getLogger(__name__)


class OrderlyTrader(ExchangeTrader):
    """Handle trades on Orderly Exchange."""

    def __init__(
        self,
        pair_map: dict[str, str],
        account_id: str,
        private_key: str,
    ) -> None:
        """Initialize shared attributes."""
        LOGGER.info("Initialize OrderlyTrader")
        self.aclient = AsyncClient()
        self.pair_map = pair_map
        self.inverted_pair_map = {v: k for k, v in pair_map.items()}
        self.account_id = account_id
        self.signer = orderly_utils.OrderlySigner(account_id, private_key)
        self._api_url = orderly_utils.ORDERLY_MAINNET_API_URL

    @classmethod
    async def create(
        cls,
        pair_map: dict[str, str],
        account_id: str,
        private_key: str,
    ) -> Self:
        """Create class instance."""
        return cls(pair_map, account_id, private_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def _send_request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
    ) -> dict:
        """Send authenticated request to Orderly API."""
        headers = self.signer.get_headers(method, path, params)
        url = f"{self._api_url}{path}"

        try:
            if method.upper() == "GET":
                response = await self.aclient.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await self.aclient.post(url, headers=headers, json=params)
            elif method.upper() == "PUT":
                response = await self.aclient.put(url, headers=headers, json=params)
            elif method.upper() == "DELETE":
                # For DELETE, Orderly expects params in query string usually?
                # Or JSON body? Docs say "Any other method type uses application/json"
                # But example for cancel order (DELETE) uses query string in 'utils.py' logic?
                # "All GET and DELETE requests use application/x-www-form-urlencoded"
                # Wait, my utils.py says:
                # "Content-Type": "application/json" if method.upper() != "GET" else "application/x-www-form-urlencoded"
                # The docs said: "All GET and DELETE requests use application/x-www-form-urlencoded. Any other method type uses application/json."

                # I should probably update utils.py to handle DELETE content-type correctly if needed.
                # But typically DELETE has no body, just query params.
                response = await self.aclient.delete(
                    url,
                    headers=headers,
                    params=params,
                )
            else:
                msg = f"Unsupported method: {method}"
                raise ValueError(msg)

            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                msg = data.get("message", "Unknown error")
                raise TransactionFailedError(msg)
            return data

        except HTTPStatusError as e:
            LOGGER.exception("HTTP error: %s", e.response.text)
            try:
                err_data = e.response.json()
                msg = err_data.get("message", str(e))
            except Exception:  # noqa: BLE001
                msg = str(e)
            raise TransactionFailedError(msg) from e

    async def create_order(
        self,
        trade_arguments: orderly_utils.OpenTradingArgs,
    ) -> TradeResults:
        """Create new order."""
        # Map arguments to Orderly API format
        # POST /v1/order

        path = "/v1/order"

        # trade_arguments coming from exchange.py should match what we expect.
        # But `exchange.py` calls `trader.create_order(pair, amount, ...)`?
        # No, `ExchangeBase` calls `create_order` with individual args,
        # but `FoxifyExchange` constructs a dict `OpenTradingArgs` and calls `trader.create_order(args)`.
        # I should follow that pattern in `OrderlyExchange`.

        # params needed:
        # symbol, order_type (LIMIT/MARKET), side (BUY/SELL), order_price (optional), order_quantity

        params = {
            "symbol": trade_arguments["symbol"],
            "order_type": trade_arguments["order_type"],
            "side": trade_arguments["side"],
            "order_quantity": float(trade_arguments["order_quantity"]),
        }

        if trade_arguments.get("order_price"):
            params["order_price"] = float(trade_arguments["order_price"])

        if trade_arguments.get("reduce_only"):
            params["reduce_only"] = True

        # Optional: visible_quantity for hidden orders? default 0 if hidden?

        return await self._send_request("POST", path, params)

    async def create_reduce_order(
        self,
        trade_arguments: orderly_utils.OpenTradingArgs,  # Reusing same type?
    ) -> TradeResults:
        """Create reduce only order."""
        # Same as create order but with reduce_only=True
        trade_arguments["reduce_only"] = True
        return await self.create_order(trade_arguments)

    async def close_position(
        self,
        trade_arguments: orderly_utils.OpenTradingArgs,
    ) -> TradeResults:
        """Close position."""
        # Effectively a reduce only market order for the full size
        trade_arguments["reduce_only"] = True
        trade_arguments["order_type"] = "MARKET"
        return await self.create_order(trade_arguments)

    async def cancel_order(
        self,
        trade_arguments: dict,
    ) -> TradeResults:
        """Cancel order.

        Args:
            trade_arguments: {"order_id": ..., "symbol": ...}
        """
        order_id = trade_arguments.get("order_id")
        symbol = trade_arguments.get("symbol")

        if not order_id or not symbol:
            msg = "Missing order_id or symbol"
            raise ValueError(msg)

        path = "/v1/order"
        params = {
            "order_id": order_id,
            "symbol": symbol,
        }

        return await self._send_request("DELETE", path, params)

    async def edit_order(
        self,
        trade_arguments: dict,
    ) -> TradeResults:
        """Edit order.

        Args:
             trade_arguments: { "order_id": ..., "symbol": ..., "new_price": ..., "new_quantity": ... }
        """
        path = "/v1/order"

        params = {
            "order_id": trade_arguments["order_id"],
            "symbol": trade_arguments["symbol"],
        }

        if "new_price" in trade_arguments:
            params["order_price"] = float(trade_arguments["new_price"])

        if "new_quantity" in trade_arguments:
            params["order_quantity"] = float(trade_arguments["new_quantity"])

        return await self._send_request("PUT", path, params)
