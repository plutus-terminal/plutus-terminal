"""Bitget Exchange."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ccxt.base.errors import ExchangeError
from ccxt.base.exchange import Decimal
import ccxt.pro
import keyring
import orjson
from qasync import asyncSlot

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.base import ExchangeBase
from plutus_terminal.core.exchange.ccxt import utils as ccxt_utils
from plutus_terminal.core.exchange.ccxt.fetcher import CCXTFetcher
from plutus_terminal.core.exchange.ccxt.trader import CCXTTrader
from plutus_terminal.core.types_ import (
    ExchangeType,
    NewAccountInfo,
    PerpsTradeDirection,
    PerpsTradeType,
)
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from typing import Self

    from plutus_terminal.core.exchange.base import ExchangeFetcherMessageBus

LOGGER = logging.getLogger(__name__)


class BitgetExchange(ExchangeBase):
    """Class to interact with Bitget exchange."""

    def __init__(self, fetcher_bus: ExchangeFetcherMessageBus) -> None:
        """Initialize shared variables."""
        super().__init__(fetcher_bus)
        keyring_account = CONFIG.current_keyring_account
        keyring_password = keyring.get_password(
            "plutus-terminal",
            str(keyring_account.username),
        )
        if keyring_password is None:
            msg = "Keyring password not found"
            raise Exception(msg)

        api_key, secret, password = orjson.loads(keyring_password)
        self.bidget_ccxt = ccxt.pro.bitget(
            {
                "apiKey": api_key,
                "secret": secret,
                "password": password,
                "enableRateLimit": True,
            },
        )

        self._pair_prefix = ""
        self._pair_separator = "/"
        self._quote_symbol = "USDT"
        self._pair_suffix = ":USDT"

        self._fetcher = CCXTFetcher(fetcher_bus, self.bidget_ccxt)
        self._trader = CCXTTrader(self.bidget_ccxt)

    @classmethod
    async def create(cls, fetcher_bus: ExchangeFetcherMessageBus) -> Self:
        """Create class instance and init_async.

        Args:
            fetcher_bus (ExchangeFetcherMessageBus): ExchangeFetcherMessageBus.

        Returns:
            CCXTExchange: Instance of FoxifyExchange.
        """
        instance = cls(fetcher_bus)
        await instance.init_async()
        return instance

    async def init_async(self) -> None:
        """Initialize async shared attributes."""
        await self.bidget_ccxt.load_markets()

    @property
    def name(self) -> str:
        """Returns: Exchange name."""
        return "bitget"

    @property
    def trader(self) -> CCXTTrader:
        """Returns: Exchange Trader."""
        return self._trader

    @property
    def fetcher(self) -> CCXTFetcher:
        """Returns: Exchange Trader."""
        return self._fetcher

    @property
    def available_pairs(self) -> set:
        """Returns set with all available pairs."""
        all_symbols = self.bidget_ccxt.symbols
        if not all_symbols:
            return set()
        return {
            symbol
            for symbol in all_symbols
            if symbol[: -len(self._pair_suffix)].endswith(self._quote_symbol)
        }

    @property
    def pair_prefix(self) -> str:
        """Returns pair prefix if any."""
        return self._pair_prefix

    @property
    def pair_separator(self) -> str:
        """Returns the pair separator if any."""
        return self._pair_separator

    @property
    def quote_symbol(self) -> str:
        """Return quote symbol."""
        return self._quote_symbol

    @property
    def pair_suffix(self) -> str:
        """Returns pair suffix."""
        return self._pair_suffix

    @property
    def cached_prices(self) -> dict:
        """Return all prices cache."""
        return self.fetcher._cached_prices  # noqa: SLF001

    @asyncSlot()
    async def set_all_leverage(self, leverage: int) -> None:
        """Set leverage for all positions.

        Args:
            leverage (int): Leverage to set.
        """
        toast_id = Toast.show_message(
            f"Setting leverage to all pairs: {leverage}x",
            type_=ToastType.WARNING,
        )
        for x, pair in enumerate(self.available_pairs):
            Toast.update_message(
                toast_id,
                f"Setting leverage to {leverage}x {x}/{len(self.available_pairs)}: {pair}",
                type_=ToastType.WARNING,
            )
            try:
                await self.bidget_ccxt.set_leverage(leverage, pair)
                LOGGER.debug("Set leverage for %s to %s", pair, leverage)
            except ExchangeError:
                # If error fetch max leverage and set it
                Toast.update_message(
                    toast_id,
                    f"Error setting leverage for pair: {pair}",
                    type_=ToastType.ERROR,
                )
                leverage_tiers = await self.bidget_ccxt.fetch_market_leverage_tiers(
                    pair,
                )
                max_leverage = int(leverage_tiers[0]["maxLeverage"])  # type: ignore

                Toast.update_message(
                    toast_id,
                    f"Setting leverage to {max_leverage}x {x}/{len(self.available_pairs)}: {pair}",
                    type_=ToastType.WARNING,
                )
                await self.bidget_ccxt.set_leverage(max_leverage, pair)
                LOGGER.debug("Set leverage for %s to %s", pair, max_leverage)

        CONFIG.leverage = leverage

        Toast.update_message(
            toast_id,
            f"Leverage set to all pairs: {leverage}x",
            type_=ToastType.SUCCESS,
        )

    @asyncSlot()
    async def set_leverage(self, coin: str, leverage: int) -> None:
        """Set leverage for pair.

        Args:
            coin (str): Coin to set leverage for.
            leverage (int): Leverage to set.
        """
        pair = self.format_pair_from_coin(coin)
        toast_id = Toast.show_message(
            f"Setting leverage from {pair} to {leverage}x",
            type_=ToastType.WARNING,
        )
        try:
            await self.bidget_ccxt.set_leverage(leverage, pair)
            LOGGER.debug("Set leverage from %s to %s", pair, leverage)
        except ExchangeError:
            # If error fetch max leverage and set it
            Toast.update_message(
                toast_id,
                f"Error setting leverage for: {pair}",
                type_=ToastType.ERROR,
            )
            leverage_tiers = await self.bidget_ccxt.fetch_market_leverage_tiers(pair)
            max_leverage = int(leverage_tiers[0]["maxLeverage"])  # type: ignore

            Toast.update_message(
                toast_id,
                f"Setting leverage of {pair} to {max_leverage}x",
                type_=ToastType.WARNING,
            )
            await self.bidget_ccxt.set_leverage(max_leverage, pair)
            LOGGER.debug("Set leverage for %s to %s", pair, max_leverage)

        Toast.update_message(
            toast_id,
            f"Leverage of {pair} set to: {leverage}x",
            type_=ToastType.SUCCESS,
        )
        CONFIG.leverage = leverage

    @asyncSlot()
    async def create_order(
        self,
        pair: str,
        amount: Decimal,
        trade_direction: PerpsTradeDirection,
        trade_type: PerpsTradeType,
        execution_price: Optional[Decimal] = None,
    ) -> None:
        """Open position for trade.

        Args:
            pair (str): Pair to open trade for.
            amount (Decimal): Value in stable to open trade for, this will be multiplied
                by de configured leverage.
            trade_direction (TradeDirection): Trade direction.
            trade_type (TradeType): Trade type.
            execution_price (Optional[Decimal], optional): Execution price.
        """
        toast_id = Toast.show_message(
            f"Opening position for {pair}",
            type_=ToastType.WARNING,
        )

        # Get cached price if available otherwise fetch it.
        try:
            current_price = Decimal(self.cached_prices[pair]["price"])
        except KeyError:
            current_price_data = await self.fetcher.fetch_current_price(pair)
            current_price = Decimal(current_price_data["price"])

        if trade_direction == PerpsTradeDirection.LONG:
            if CONFIG.take_profit == 0:
                take_profit = current_price
            else:
                take_profit = current_price * (1 + Decimal(CONFIG.take_profit / 100))
            if CONFIG.stop_loss == 0:
                stop_loss = current_price
            else:
                stop_loss = current_price * (1 - Decimal(CONFIG.stop_loss / 100))
        else:
            if CONFIG.take_profit == 0:
                take_profit = current_price
            else:
                take_profit = current_price * (1 - Decimal(CONFIG.take_profit / 100))
            if CONFIG.stop_loss == 0:
                stop_loss = current_price
            else:
                stop_loss = current_price * (1 + Decimal(CONFIG.stop_loss / 100))

        # Convert amount with leverage to base asset
        amount = (amount * Decimal(CONFIG.leverage)) / current_price

        trading_args = ccxt_utils.TradingArgs(
            {
                "pair": pair,
                "trade_type": trade_type,
                "side": trade_direction,
                "price": current_price,
                "amount": amount,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
            },
        )
        try:
            await self.trader.create_order(trading_args)
        except TransactionFailedError as error:
            Toast.update_message(
                toast_id,
                f"Failed to open position > {error}",
                type_=ToastType.ERROR,
            )
        Toast.update_message(
            toast_id,
            f"Position opened for {pair}",
            type_=ToastType.SUCCESS,
        )

    async def stop(self) -> None:
        """Stop all async tasks and cleanup for deletion."""
        await super().stop()
        await self.bidget_ccxt.close()

    @staticmethod
    def new_account_info() -> NewAccountInfo:
        """Provide info for new account creation."""
        return NewAccountInfo(
            referral_link="",
            secrets=["API Key", "Secret", "Passphrase"],
        )

    @staticmethod
    def exchange_type() -> ExchangeType:
        """Return exchange type."""
        return ExchangeType.CEX

    @staticmethod
    def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
        """Validate secrets."""
        import ccxt

        try:
            exchange = ccxt.bitget(
                {
                    "apiKey": secrets[0],
                    "secret": secrets[1],
                    "password": secrets[2],
                    "enableRateLimit": True,
                },
            )
            exchange.fetch_balance()
        except Exception:  # noqa: BLE001
            return False, "Invalid API credentials"
        else:
            return True, "Valid API credentials."
