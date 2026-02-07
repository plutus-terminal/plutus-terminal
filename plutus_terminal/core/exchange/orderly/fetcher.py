"""Fetcher implementation for Orderly exchange."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping
import contextlib
from decimal import Decimal
import logging
import time
from typing import TYPE_CHECKING, Any, Optional, cast

from httpx import HTTPStatusError, RequestError
import pandas
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
)

from plutus_terminal.core.exchange.base import ExchangeFetcher
from plutus_terminal.core.exchange.orderly.ws_topics import (
    ACCOUNT_TOPICS,
    USDC_SETTLEMENT_TOKEN,
    bbo_topic,
    mark_price_topic,
)
from plutus_terminal.core.exchange.types import OrderData, PerpsTradeType
from plutus_terminal.core.types_ import PerpsPosition, PerpsTradeDirection, PriceData, PriceHistory
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from plutus_terminal.core.exchange.orderly.markets import OrderlyMarketRegistry
    from plutus_terminal.core.exchange.orderly.rest_client import OrderlyRestClient
    from plutus_terminal.core.exchange.orderly.websocket import OrderlyWebsocketManager
    from plutus_terminal.message_bus import MessageBus


LOGGER = logging.getLogger(__name__)
_KLINE_MIN_FIELDS = 5
_SECONDS_TO_MS_THRESHOLD = 10_000_000_000
_KLINE_HISTORY_RETRY_ATTEMPTS = 7
_KLINE_MIN_WINDOW_SECONDS = 120
_HTTP_SERVER_ERROR_MIN = 500
_HTTP_SERVER_ERROR_MAX = 600
_HTTP_TOO_MANY_REQUESTS = 429
_KLINE_HISTORY_RATE_LIMIT_INTERVAL_SECONDS = 0.25
_KLINE_HISTORY_RETRY_BASE_SECONDS = 0.5
_KLINE_HISTORY_RETRY_MAX_SECONDS = 12.0
_KLINE_HISTORY_429_MIN_BACKOFF_SECONDS = 1.0


def _is_retryable_history_status_error(exception: BaseException) -> bool:
    """Return True when kline history HTTP status is retryable."""
    if not isinstance(exception, HTTPStatusError):
        return False
    status_code = exception.response.status_code
    return status_code == _HTTP_TOO_MANY_REQUESTS or (
        _HTTP_SERVER_ERROR_MIN <= status_code < _HTTP_SERVER_ERROR_MAX
    )


def _history_retry_wait(retry_state: RetryCallState) -> float:
    """Return adaptive retry delay for history requests."""
    attempt = max(1, int(retry_state.attempt_number))
    exponential_seconds = min(
        _KLINE_HISTORY_RETRY_MAX_SECONDS,
        _KLINE_HISTORY_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
    )

    exception = retry_state.outcome.exception() if retry_state.outcome is not None else None
    retry_after_seconds = _extract_retry_after_seconds(exception)
    if retry_after_seconds is not None:
        return retry_after_seconds

    if (
        isinstance(exception, HTTPStatusError)
        and exception.response.status_code == _HTTP_TOO_MANY_REQUESTS
    ):
        return max(_KLINE_HISTORY_429_MIN_BACKOFF_SECONDS, exponential_seconds)
    return exponential_seconds


def _extract_retry_after_seconds(exception: BaseException | None) -> float | None:
    """Extract Retry-After header value in seconds when available."""
    if not isinstance(exception, HTTPStatusError):
        return None
    header_value = exception.response.headers.get("Retry-After")
    if header_value is None:
        return None
    try:
        return max(0.0, float(header_value))
    except ValueError:
        return None


class OrderlyFetcher(ExchangeFetcher):
    """Fetch market and account data with websocket-first design."""

    def __init__(
        self,
        rest_client: OrderlyRestClient,
        websocket_manager: OrderlyWebsocketManager,
        market_registry: OrderlyMarketRegistry,
        message_bus: MessageBus,
    ) -> None:
        """Initialize fetcher dependencies and runtime caches."""
        self._rest_client = rest_client
        self._ws = websocket_manager
        self._market_registry = market_registry
        self._message_bus = message_bus

        self._cached_prices: dict[str, PriceData] = {}
        self._cached_stable_balance = Decimal(0)
        self._cached_unsettled_pnl = Decimal(0)
        self._cached_positions: list[PerpsPosition] = []
        self._cached_orders: list[OrderData] = []
        self._connection_count: dict[str, int] = defaultdict(int)
        self._in_flight_history_requests: dict[
            tuple[str, str, int, int],
            asyncio.Task[dict[str, Any]],
        ] = {}
        self._history_request_pacing_lock = asyncio.Lock()
        self._history_request_semaphore = asyncio.Semaphore(1)
        self._last_history_request_monotonic = 0.0
        self._history_rate_limited_until_monotonic = 0.0
        self._stop_event = asyncio.Event()
        self._private_consumer_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Connect sockets and subscribe default private topics."""
        await self._ws.ensure_connections()
        await self._ws.subscribe_private(ACCOUNT_TOPICS)
        if self._private_consumer_task is None:
            self._private_consumer_task = asyncio.create_task(self._consume_private_events())

    async def fetch_price_history(
        self,
        pair: str,
        from_timestamp: int,
        to_timestamp: int,
        resolution: str,
    ) -> PriceHistory:
        """Fetch candle history for the selected pair."""
        symbol = self._market_registry.get_symbol_for_pair(pair)
        normalized_from = _normalize_unix_seconds(from_timestamp)
        normalized_to = _normalize_unix_seconds(to_timestamp)
        if normalized_from >= normalized_to:
            normalized_from = max(0, normalized_to - _KLINE_MIN_WINDOW_SECONDS)

        payload = await self._request_chart_history(
            symbol,
            _resolution_to_orderly_resolution(resolution),
            normalized_from,
            normalized_to,
        )

        timestamps, opens, highs, lows, closes = _extract_history_series(payload)

        date: list[pandas.Timestamp] = []
        open_: list[float] = []
        high: list[float] = []
        low: list[float] = []
        close: list[float] = []

        for timestamp, open_price, high_price, low_price, close_price in zip(
            timestamps,
            opens,
            highs,
            lows,
            closes,
            strict=False,
        ):
            date.append(_timestamp_to_pandas(timestamp))
            open_.append(float(open_price))
            high.append(float(high_price))
            low.append(float(low_price))
            close.append(float(close_price))

        return {
            "date": date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        }

    async def _request_chart_history(
        self,
        symbol: str,
        resolution: str,
        from_timestamp: int,
        to_timestamp: int,
    ) -> dict[str, Any]:
        """Request chart history while coalescing duplicate in-flight requests."""
        cache_key = (symbol, resolution, from_timestamp, to_timestamp)
        current_request = self._in_flight_history_requests.get(cache_key)
        if current_request is not None:
            return await asyncio.shield(current_request)

        created_request: asyncio.Task[dict[str, Any]] = asyncio.create_task(
            self._request_chart_history_with_retry(
                symbol=symbol,
                resolution=resolution,
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
            )
        )
        self._in_flight_history_requests[cache_key] = created_request
        try:
            return await asyncio.shield(created_request)
        finally:
            self._in_flight_history_requests.pop(cache_key, None)

    @retry(
        retry=(
            retry_if_exception_type(RequestError)
            | retry_if_exception(_is_retryable_history_status_error)
        ),
        stop=stop_after_attempt(_KLINE_HISTORY_RETRY_ATTEMPTS),
        wait=_history_retry_wait,
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
        reraise=True,
    )
    async def _request_chart_history_with_retry(
        self,
        symbol: str,
        resolution: str,
        from_timestamp: int,
        to_timestamp: int,
    ) -> dict[str, Any]:
        """Request chart history with retries and local pacing."""
        async with self._history_request_semaphore:
            await self._wait_for_history_request_slot()
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "from": str(from_timestamp),
                "to": str(to_timestamp),
            }
            try:
                return await self._rest_client.request_public(
                    "GET", "/v1/tv/history", params=params
                )
            except HTTPStatusError as error:
                self._register_history_rate_limit(error)
                raise

    async def _wait_for_history_request_slot(self) -> None:
        """Space history requests to reduce endpoint burst pressure."""
        async with self._history_request_pacing_lock:
            now_monotonic = time.monotonic()
            if now_monotonic < self._history_rate_limited_until_monotonic:
                await asyncio.sleep(self._history_rate_limited_until_monotonic - now_monotonic)
                now_monotonic = time.monotonic()
            elapsed_seconds = now_monotonic - self._last_history_request_monotonic
            if elapsed_seconds < _KLINE_HISTORY_RATE_LIMIT_INTERVAL_SECONDS:
                await asyncio.sleep(_KLINE_HISTORY_RATE_LIMIT_INTERVAL_SECONDS - elapsed_seconds)
            self._last_history_request_monotonic = time.monotonic()

    def _register_history_rate_limit(self, exception: HTTPStatusError) -> None:
        """Apply shared cooldown when kline history is rate-limited."""
        if exception.response.status_code != _HTTP_TOO_MANY_REQUESTS:
            return
        retry_after_seconds = _extract_retry_after_seconds(exception)
        cooldown_seconds = (
            retry_after_seconds
            if retry_after_seconds is not None
            else _KLINE_HISTORY_429_MIN_BACKOFF_SECONDS
        )
        self._history_rate_limited_until_monotonic = max(
            self._history_rate_limited_until_monotonic,
            time.monotonic() + cooldown_seconds,
        )

    async def subscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Subscribe to public price topics for one pair."""
        await self.start()
        self._connection_count[pair] += 1
        if self._connection_count[pair] > 1 and not force:
            return

        symbol = self._market_registry.get_symbol_for_pair(pair)
        await self._ws.subscribe_public((bbo_topic(symbol), mark_price_topic(symbol)))

    async def resubscribe_on_going_connections(self) -> None:
        """Resubscribe all active pair subscriptions."""
        for pair, count in self._connection_count.items():
            if count < 1:
                continue
            await self.subscribe_to_price(pair, force=True)
            self._connection_count[pair] -= 1

    async def unsubscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Unsubscribe from public price topics for one pair."""
        await self.start()
        self._connection_count[pair] -= 1
        if self._connection_count[pair] > 0 and not force:
            return

        symbol = self._market_registry.get_symbol_for_pair(pair)
        await self._ws.unsubscribe_public((bbo_topic(symbol), mark_price_topic(symbol)))
        self._connection_count[pair] = 0
        self._cached_prices.pop(pair, None)

    async def receive_subscribed_prices(self) -> None:
        """Read public websocket events and update cached prices."""
        await self.start()
        while not self._stop_event.is_set() and not self._ws.should_stop():
            try:
                event = await self._ws.next_public_event()
                topic = str(event.get("topic", ""))
                if not topic:
                    continue
                pair = _pair_from_topic(topic)
                if pair is None:
                    continue
                price = _extract_price_from_event(event)
                if price is None:
                    continue

                self._cached_prices[pair] = {
                    "price": price,
                    "date": _now_timestamp(),
                }
                self._message_bus.subscribed_prices_fetched.emit(self._cached_prices)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Unexpected error while receiving public Orderly prices")
                await asyncio.sleep(0.2)
                await self._ws.connect_public()
                await self.resubscribe_on_going_connections()

    async def watch_all_positions(self) -> None:
        """Emit positions from cache and refresh snapshot periodically."""
        while not self._stop_event.is_set():
            await self._refresh_positions()
            self._message_bus.positions_fetched.emit(self._cached_positions)
            await asyncio.sleep(1)

    async def fetch_all_positions(self) -> list[PerpsPosition]:
        """Fetch all open positions from private REST endpoint."""
        payload = await self._rest_client.request_private("GET", "/v1/positions")
        rows = payload.get("data", {}).get("rows", [])
        self._cached_unsettled_pnl = _sum_unsettled_pnl(rows)
        parsed_positions = [_parse_position(row, self._market_registry) for row in rows]
        self._cached_positions = [position for position in parsed_positions if position is not None]
        self._message_bus.balance_fetched.emit(self._balance_with_unsettled_pnl())
        return self._cached_positions

    async def watch_all_orders(self) -> None:
        """Emit open orders from cache and refresh snapshot periodically."""
        await self._refresh_orders()
        while not self._stop_event.is_set():
            self._message_bus.orders_fetched.emit(self._cached_orders)
            await asyncio.sleep(1)

    async def fetch_all_orders(self) -> list[OrderData]:
        """Fetch all incomplete orders from private REST endpoint."""
        payload = await self._rest_client.request_private(
            "GET",
            "/v1/orders",
            params={"status": "INCOMPLETE"},
        )
        rows = payload.get("data", {}).get("rows", [])
        parsed_orders = [_parse_order(row, self._market_registry) for row in rows]
        self._cached_orders = [order for order in parsed_orders if order is not None]
        return self._cached_orders

    async def fetch_price_at_time(self, pair: str, timestamp: int) -> PriceData:
        """Fetch price for pair close to a timestamp."""
        history = await self.fetch_price_history(
            pair=pair,
            from_timestamp=timestamp - 120,
            to_timestamp=timestamp,
            resolution="1",
        )
        if not history["close"]:
            return await self.fetch_current_price(pair)
        return {
            "price": Decimal(str(history["close"][-1])),
            "date": history["date"][-1],
        }

    async def fetch_current_price(self, pair: str) -> PriceData:
        """Fetch current mark price from cache or public endpoint fallback."""
        cached = self._cached_prices.get(pair)
        if cached is not None:
            return cached

        symbol = self._market_registry.get_symbol_for_pair(pair)
        payload = await self._rest_client.request_public("GET", f"/v1/public/info/{symbol}")
        mark_price = Decimal(str(payload.get("data", {}).get("mark_price", "0")))
        return {
            "price": mark_price,
            "date": _now_timestamp(),
        }

    async def watch_stable_balance(self) -> None:
        """Emit stable balance from cache and refresh snapshot periodically."""
        await self._refresh_balance()
        while not self._stop_event.is_set():
            self._message_bus.balance_fetched.emit(self._balance_with_unsettled_pnl())
            await asyncio.sleep(1)

    async def fetch_stable_balance(self) -> Decimal:
        """Fetch stable token balance from private holdings endpoint."""
        payload = await self._rest_client.request_private("GET", "/v1/client/holding")
        rows = payload.get("data", {}).get("holding", [])
        for row in rows:
            token = str(row.get("token", ""))
            if token != USDC_SETTLEMENT_TOKEN:
                continue
            return _available_balance_from_row(row)
        return Decimal(0)

    def get_position_associated_with_order(self, order: OrderData) -> Optional[PerpsPosition]:
        """Get currently cached position associated with given order."""
        for position in self._cached_positions:
            if (
                position["pair"] == order["pair"]
                and position["trade_direction"] == order["trade_direction"]
            ):
                return position
        return None

    def calculate_margin_fee(self, position_size: Decimal) -> Decimal:
        """Estimate margin fee using a default taker fee rate."""
        return position_size * Decimal("0.0006")

    def fetch_funding_fee(self, perps_position: PerpsPosition) -> Decimal:  # noqa: ARG002
        """Return funding fee for position.

        Funding values are delivered by execution/account topics on Orderly;
        this integration currently returns zero in UI estimates.
        """
        return Decimal(0)

    def calculate_liquidation_price(self, perps_position: PerpsPosition) -> Decimal:
        """Estimate liquidation price from open price and dynamic effective leverage."""
        position_size = perps_position["position_size_stable"]
        collateral = perps_position["collateral_stable"]
        available_balance = self._balance_with_unsettled_pnl()
        effective_margin = collateral + available_balance

        leverage = perps_position["leverage"]
        if position_size > Decimal(0) and effective_margin > Decimal(0):
            leverage = position_size / effective_margin

        return _estimate_liquidation_price(
            open_price=perps_position["open_price"],
            leverage=leverage,
            trade_direction=perps_position["trade_direction"],
        )

    def calculate_pnl_percent_before_fees(
        self,
        perps_position: PerpsPosition,
        current_price: Optional[Decimal],
    ) -> Decimal:
        """Calculate PnL percent before fees from current price."""
        if current_price is None:
            cached = self._cached_prices.get(perps_position["pair"])
            if cached is None:
                return Decimal(0)
            current_price = cached["price"]

        open_price = perps_position["open_price"]
        if open_price <= Decimal(0):
            return Decimal(0)
        price_change = ((current_price - open_price) / open_price) * 100
        if perps_position["trade_direction"] is PerpsTradeDirection.SHORT:
            price_change *= Decimal(-1)
        return price_change * perps_position["leverage"]

    async def stop_async(self) -> None:
        """Stop loops and close websocket/rest resources."""
        self._stop_event.set()
        if self._private_consumer_task is not None:
            self._private_consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._private_consumer_task
        await self._ws.stop()
        await self._rest_client.aclose()

    async def _consume_private_events(self) -> None:
        """Consume private websocket topics and update account caches."""
        while not self._stop_event.is_set() and not self._ws.should_stop():
            try:
                event = await self._ws.next_private_event()
                topic = str(event.get("topic", ""))
                if "balance" in topic or topic == "account":
                    await self._apply_balance_event(event)
                if "position" in topic:
                    await self._apply_positions_event(event)
                if "execution" in topic or "order" in topic:
                    await self._refresh_orders()
                    await self._refresh_positions()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Unexpected error while consuming private Orderly events")
                await asyncio.sleep(0.2)
                await self._ws.connect_private()
                await self._ws.subscribe_private(ACCOUNT_TOPICS)

    async def _apply_balance_event(self, event: dict[str, Any]) -> None:
        """Extract and apply balance updates from private stream event."""
        data = event.get("data")
        if isinstance(data, dict):
            balances = data.get("balances", data.get("holding", []))
        else:
            balances = data if isinstance(data, list) else []

        usdc_balance = _extract_usdc_balance_from_event_payload(balances)
        if usdc_balance is None:
            return
        self._cached_stable_balance = usdc_balance
        self._message_bus.balance_fetched.emit(self._balance_with_unsettled_pnl())

    async def _apply_positions_event(self, event: dict[str, Any]) -> None:
        """Extract and apply positions updates from private stream event."""
        data = event.get("data", {})
        rows = data if isinstance(data, list) else data.get("rows", data.get("positions", []))
        self._cached_unsettled_pnl = _sum_unsettled_pnl(rows)
        parsed = [_parse_position(row, self._market_registry) for row in rows]
        self._cached_positions = [position for position in parsed if position is not None]
        self._message_bus.positions_fetched.emit(self._cached_positions)
        self._message_bus.balance_fetched.emit(self._balance_with_unsettled_pnl())

    async def _refresh_positions(self) -> None:
        """Refresh positions cache from private REST endpoint."""
        try:
            await self.fetch_all_positions()
        except Exception:
            LOGGER.exception("Failed to refresh Orderly positions snapshot")

    async def _refresh_orders(self) -> None:
        """Refresh orders cache from private REST endpoint."""
        try:
            await self.fetch_all_orders()
        except Exception:
            LOGGER.exception("Failed to refresh Orderly orders snapshot")

    async def _refresh_balance(self) -> None:
        """Refresh stable balance cache from private REST endpoint."""
        try:
            self._cached_stable_balance = await self.fetch_stable_balance()
        except Exception:
            LOGGER.exception("Failed to refresh Orderly balance snapshot")

    def _balance_with_unsettled_pnl(self) -> Decimal:
        """Return available balance adjusted by unsettled PnL."""
        return self._cached_stable_balance + self._cached_unsettled_pnl


def _resolution_to_orderly_resolution(resolution: str) -> str:
    """Map terminal chart resolution to Orderly TradingView resolution."""
    if resolution in {"1", "5", "15", "30", "60", "240"}:
        return resolution
    return "1"


def _available_balance_from_row(row: Mapping[str, Any]) -> Decimal:
    """Compute available balance from holding and reserved amounts."""
    holding = _decimal_field(row, "holding")
    if holding == Decimal(0):
        holding = _decimal_field(row, "balance")

    frozen = _decimal_field(row, "frozen")
    pending_short = _decimal_field(row, "pending_short")
    if pending_short == Decimal(0):
        pending_short = _decimal_field(row, "pendingShortQty")

    available = holding - frozen - pending_short
    if available < Decimal(0):
        return Decimal(0)
    return available


def _extract_usdc_balance_from_event_payload(payload: object) -> Decimal | None:
    """Extract available USDC balance from websocket event payload."""
    if isinstance(payload, Mapping):
        direct_balance = payload.get(USDC_SETTLEMENT_TOKEN)
        if isinstance(direct_balance, Mapping):
            return _available_balance_from_row(direct_balance)

        for token, row in payload.items():
            if str(token) != USDC_SETTLEMENT_TOKEN or not isinstance(row, Mapping):
                continue
            return _available_balance_from_row(row)
        return None

    if not isinstance(payload, list):
        return None

    for row in payload:
        if not isinstance(row, Mapping):
            continue
        token = str(row.get("token", ""))
        if token != USDC_SETTLEMENT_TOKEN:
            continue
        return _available_balance_from_row(row)
    return None


def _decimal_field(row: Mapping[str, Any], field: str) -> Decimal:
    """Read Decimal field from mapping with zero default."""
    return Decimal(str(row.get(field, "0")))


def _sum_unsettled_pnl(rows: object) -> Decimal:
    """Sum unsettled PnL values from position payload rows."""
    if not isinstance(rows, list):
        return Decimal(0)

    total = Decimal(0)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        total += _decimal_field(row, "unsettled_pnl")
    return total


def _normalize_unix_seconds(timestamp: float | str) -> int:
    """Normalize numeric-like timestamp into integer Unix seconds."""
    timestamp_float = float(timestamp)
    if timestamp_float >= _SECONDS_TO_MS_THRESHOLD:
        return int(timestamp_float // 1000)
    return int(timestamp_float)


def _extract_history_series(
    payload: dict[str, Any],
) -> tuple[list[Any], list[Any], list[Any], list[Any], list[Any]]:
    """Extract OHLC and time series from public TradingView or legacy row payloads."""
    payload_data = payload.get("data")
    source = payload_data if isinstance(payload_data, dict) else payload

    if isinstance(source, dict) and all(key in source for key in ("t", "o", "h", "l", "c")):
        timestamps = list(cast("list[Any]", source.get("t", [])))
        opens = list(cast("list[Any]", source.get("o", [])))
        highs = list(cast("list[Any]", source.get("h", [])))
        lows = list(cast("list[Any]", source.get("l", [])))
        closes = list(cast("list[Any]", source.get("c", [])))
        return timestamps, opens, highs, lows, closes

    rows = payload.get("data", {}).get("rows", [])
    row_timestamps: list[Any] = []
    row_opens: list[Any] = []
    row_highs: list[Any] = []
    row_lows: list[Any] = []
    row_closes: list[Any] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < _KLINE_MIN_FIELDS:
            continue
        row_timestamps.append(row[0])
        row_opens.append(row[1])
        row_highs.append(row[2])
        row_lows.append(row[3])
        row_closes.append(row[4])
    return row_timestamps, row_opens, row_highs, row_lows, row_closes


def _timestamp_to_pandas(timestamp: int | str) -> pandas.Timestamp:
    """Convert seconds or milliseconds timestamp into pandas.Timestamp."""
    timestamp_int = int(timestamp)
    unit = "ms" if timestamp_int >= _SECONDS_TO_MS_THRESHOLD else "s"
    return cast("pandas.Timestamp", pandas.Timestamp(timestamp_int, unit=unit))


def _pair_from_topic(topic: str) -> str | None:
    """Convert websocket topic to terminal pair name."""
    if "@" not in topic:
        return None
    symbol = topic.split("@", maxsplit=1)[0]
    if not symbol.startswith("PERP_"):
        return None
    _, base, quote = symbol.split("_", 2)
    return f"Crypto.{base}/{quote}"


def _extract_price_from_event(event: dict[str, Any]) -> Decimal | None:
    """Extract Decimal price from public topic event payload."""
    data = event.get("data")
    if isinstance(data, dict):
        if "mark_price" in data:
            return Decimal(str(data["mark_price"]))
        if "close" in data:
            return Decimal(str(data["close"]))
        if "price" in data:
            return Decimal(str(data["price"]))
        if "b" in data and "a" in data:
            bid = Decimal(str(data["b"]))
            ask = Decimal(str(data["a"]))
            return (bid + ask) / 2
    return None


def _now_timestamp() -> pandas.Timestamp:
    """Return current UTC timestamp object."""
    return pandas.Timestamp.utcnow()


def _estimate_liquidation_price(
    open_price: Decimal,
    leverage: Decimal,
    trade_direction: PerpsTradeDirection,
) -> Decimal:
    """Estimate liquidation price from open price and leverage."""
    if leverage <= Decimal(0) or open_price <= Decimal(0):
        return Decimal(0)

    buffer = Decimal("0.98") / leverage
    if trade_direction is PerpsTradeDirection.LONG:
        return open_price * (Decimal(1) - buffer)
    return open_price * (Decimal(1) + buffer)


def _parse_position(
    row: dict[str, Any],
    market_registry: OrderlyMarketRegistry,
) -> PerpsPosition | None:
    """Parse Orderly position row into terminal position schema."""
    if not isinstance(row, dict):
        return None
    symbol = str(row.get("symbol", ""))
    if symbol == "":
        return None
    try:
        rule = market_registry.get_rule_by_symbol(symbol)
    except KeyError:
        return None

    position_qty = Decimal(str(row.get("position_qty", "0")))
    abs_qty = abs(position_qty)
    if abs_qty == Decimal(0):
        return None

    mark_price = Decimal(str(row.get("mark_price", row.get("average_open_price", "0"))))
    open_price = Decimal(str(row.get("average_open_price", mark_price)))
    notional = abs_qty * open_price
    leverage = Decimal(str(row.get("leverage", "1")))
    if leverage <= Decimal(0):
        leverage = Decimal(1)

    direction = PerpsTradeDirection.LONG if position_qty > 0 else PerpsTradeDirection.SHORT
    liquidation_price = Decimal(
        str(
            row.get(
                "liquidation_price",
                row.get(
                    "est_liquidation_price", row.get("est_liq_price", row.get("liq_price", "0"))
                ),
            ),
        ),
    )
    if liquidation_price <= Decimal(0):
        liquidation_price = _estimate_liquidation_price(open_price, leverage, direction)

    position_id = int(row.get("position_id", 0))
    if position_id == 0:
        position_id = _fallback_position_id(symbol=symbol, trade_direction=direction)

    return {
        "pair": rule.pair,
        "id": position_id,
        "position_size_stable": notional,
        "collateral_stable": notional / leverage,
        "open_price": open_price,
        "trade_direction": direction,
        "leverage": leverage,
        "liquidation_price": liquidation_price,
        "extra": {"symbol": symbol, "base_size": str(abs_qty)},
    }


def _fallback_position_id(symbol: str, trade_direction: PerpsTradeDirection) -> int:
    """Build deterministic position identifier when API id is unavailable."""
    direction_tag = "LONG" if trade_direction is PerpsTradeDirection.LONG else "SHORT"
    source = f"{symbol}:{direction_tag}"
    checksum = 0
    for character in source:
        checksum = (checksum * 131 + ord(character)) % 2_147_483_647
    return checksum


def _parse_order(
    row: dict[str, Any],
    market_registry: OrderlyMarketRegistry,
) -> OrderData | None:
    """Parse Orderly order row into terminal order schema."""
    if not isinstance(row, dict):
        return None
    symbol = str(row.get("symbol", ""))
    if symbol == "":
        return None
    try:
        rule = market_registry.get_rule_by_symbol(symbol)
    except KeyError:
        return None

    side = str(row.get("side", "BUY"))
    direction = PerpsTradeDirection.LONG if side == "BUY" else PerpsTradeDirection.SHORT
    order_type_raw = str(row.get("order_type", "LIMIT"))
    order_type = PerpsTradeType.MARKET if order_type_raw == "MARKET" else PerpsTradeType.LIMIT

    trigger_price = Decimal(str(row.get("trigger_price", row.get("order_price", "0"))))
    order_qty = Decimal(str(row.get("order_quantity", "0")))
    size_stable = order_qty * trigger_price

    return {
        "id": str(row.get("order_id", row.get("client_order_id", ""))),
        "pair": rule.pair,
        "trigger_price": trigger_price,
        "size_stable": size_stable,
        "trade_direction": direction,
        "order_type": order_type,
        "reduce_only": bool(row.get("reduce_only", False)),
        "extra": {"symbol": symbol},
    }
