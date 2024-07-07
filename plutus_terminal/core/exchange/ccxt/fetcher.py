"""Base fetcher for CCTX api."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from decimal import Decimal
import logging
import math
from typing import TYPE_CHECKING

import pandas
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from plutus_terminal.core.exchange.base import (
    ExchangeFetcher,
)
from plutus_terminal.core.types_ import PerpsPosition, PerpsTradeDirection, PriceData
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    import ccxt.pro

    from plutus_terminal.core.exchange.base import ExchangeFetcherMessageBus
    from plutus_terminal.core.types_ import PriceHistory

LOGGER = logging.getLogger(__name__)


class CCXTFetcher(ExchangeFetcher):
    """Base class for CCTX fetcher."""

    def __init__(
        self,
        message_bus: ExchangeFetcherMessageBus,
        exchange_instance: ccxt.pro.Exchange,
    ) -> None:
        """Initialize shared attributes."""
        self._cctx = exchange_instance
        self._message_bus = message_bus
        self.connection_count: dict[str, int] = defaultdict(int)
        self._watched_tickers: set[str] = set()
        self._cached_prices: dict[str, PriceData] = {}
        self._synced = True
        self.async_stop_event = asyncio.Event()

    async def fetch_price_history(
        self,
        pair: str,
        from_timestamp: int,
        resolution: str,
    ) -> PriceHistory:
        """Fetch the price history of pair for the given start and end time.

        Args:
            pair (str): Pair to fetch.
            from_timestamp (int): Timestamp for the leftmost bar in secods
            resolution (str): Bar resolution in seconds.

        Returns:
            PriceHistory: Dict with ohlcv.
        """
        # Transform seconds to miliseconds
        from_timestamp = int(from_timestamp * 1000)
        match resolution:
            case "5":
                resolution = "5m"
            case "15":
                resolution = "15m"
            case "30":
                resolution = "30m"
            case "60":
                resolution = "1h"
            case "240":
                resolution = "4h"
            case _:
                resolution = "1m"
        ohlcvs = await self._cctx.fetch_ohlcv(
            symbol=pair,
            timeframe=resolution,
            since=from_timestamp,
            limit=200,
        )
        ohlcvs = list(map(list, zip(*ohlcvs, strict=False)))
        price_history: PriceHistory = {
            "date": [pandas.Timestamp(t, unit="ms") for t in ohlcvs[0]],
            "open": ohlcvs[1],
            "high": ohlcvs[2],
            "low": ohlcvs[3],
            "close": ohlcvs[4],
            "volume": ohlcvs[5],  # type: ignore
        }
        LOGGER.debug(
            "Fetched price history for %s from %s",
            pair,
            from_timestamp,
        )
        return price_history

    async def subscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Subscribe to receive price updates for the given pair.

        Args:
            pair (str): Pair name e.g BTC/USDT.
            force (bool, optional): Force subscribe. Defaults to False.
        """
        self.connection_count[pair] += 1
        if self.connection_count[pair] > 1 and not force:
            return
        self._watched_tickers.add(pair)
        LOGGER.info("Subscribed to receive price updates of: %s", pair)

    async def resubscribe_on_going_connections(self) -> None:
        """Resubscribe on going connections."""
        LOGGER.warning("Re-subscribing to on going connection...")
        for pair, count in self.connection_count.items():
            if count >= 1:
                await self.subscribe_to_price(pair, force=True)
                # Reduce 1 since this connection should already be present
                self.connection_count[pair] -= 1

    async def unsubscribe_to_price(self, pair: str, force: bool = False) -> None:
        """Unsubscribe to receive price updates for the given pair.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
            force (bool, optional): Force unsubscribe. Defaults to False.
        """
        self.connection_count[pair] -= 1
        if self.connection_count[pair] > 0 and not force:
            return
        self._watched_tickers.discard(pair)
        del self._cached_prices[pair]
        LOGGER.info("Unsubscribed to receive price updates of: %s", pair)

    async def receive_subscribed_prices(self) -> None:
        """Receive live data of subscribed prices from exchange."""
        while not self.async_stop_event.is_set():
            try:
                tickers = await self._cctx.watch_tickers(list(self._watched_tickers))
                for ticker in tickers.values():  # type: ignore
                    pair = ticker["symbol"]
                    self._cached_prices[pair] = PriceData(
                        {
                            "price": ticker["last"],
                            "date": pandas.Timestamp(ticker["timestamp"], unit="ms"),
                            "volume": ticker["quoteVolume"],
                        },
                    )
                    self._message_bus.subscribed_prices_signal.emit(self._cached_prices)
            except asyncio.CancelledError:
                LOGGER.debug("Watch all positions cancelled.")
                raise
            except Exception:
                LOGGER.exception("Unexpected error while receiving prices")

    @retry(
        reraise=True,
        stop=stop_after_attempt(15),
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_price_at_time(self, pair: str, timestamp: int) -> PriceData:
        """Fetch price at current time.

        Args:
            pair (str): Pair name e.g Crypto.BTC/USD.
            timestamp (int): Unix timestamp in seconds.

        Returns:
            PriceData: Price data for fetched pair.
        """
        LOGGER.debug("Fetching %s price at time: %s", pair, timestamp)
        rounded_timestamp = math.floor(timestamp / 60) * 60
        timestamp = int(rounded_timestamp * 1000)
        ticker = await self._cctx.fetch_ohlcv(
            symbol=pair,
            timeframe="1m",
            since=timestamp,
            limit=1,
        )
        return PriceData(
            {
                "price": ticker[0][4],
                "date": pandas.Timestamp(ticker[0][0], unit="ms"),
                "volume": ticker[0][6],
            },
        )

    async def watch_all_positions(self) -> None:
        """Watch all open positions for all available pairs."""
        while not self.async_stop_event.is_set():
            all_positions = []
            try:
                all_positions.extend(await self._cctx.fetch_positions())
            except asyncio.CancelledError:
                LOGGER.debug("Watch all positions cancelled.")
                raise
            except Exception:
                LOGGER.exception("Unexpected error while watching positions")
            self._message_bus.positions_signal.emit(all_positions)

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_all_positions(self) -> list[PerpsPosition]:
        """Fetch all open positions for all available pairs."""
        all_positions: list[PerpsPosition] = []
        positions = await self._cctx.fetch_positions()
        for position in positions:  # type: ignore
            position_size_stable = Decimal(position["entryPrice"]) * Decimal(
                position["contracts"] / position["leverage"],
            )
            collateral = position_size_stable / Decimal(position["leverage"])
            persp_position = PerpsPosition(
                {
                    "pair": position["symbol"],
                    "id": position["id"],
                    "position_size_stable": position_size_stable,
                    "collateral_stable": collateral,
                    "open_price": Decimal(position["entryPrice"]),
                    "trade_direction": PerpsTradeDirection[position["side"].upper()],
                    "leverage": Decimal(position["leverage"]),
                },
            )
            all_positions.append(persp_position)
        return all_positions

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_current_price(self, pair: str) -> PriceData:
        """Fetch current price of given pair."""
        ticker = await self._cctx.fetch_ticker(symbol=pair)
        return PriceData(
            {
                "price": ticker["last"],
                "date": pandas.Timestamp(ticker["timestamp"], unit="ms"),
                "volume": ticker["quoteVolume"],
            },
        )

    async def stop(self) -> None:
        """Stop infinite loops and close connections."""
        self.async_stop_event.set()
