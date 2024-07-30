"""Foxify funded exchange fetcher."""

from decimal import Decimal
import logging

from eth_typing import ChecksumAddress
from tenacity import before_sleep_log, retry, wait_exponential

from plutus_terminal.core.exchange.base import ExchangeFetcherMessageBus
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.foxify.fetcher import FoxifyFetcher
from plutus_terminal.log_utils import log_retry

LOGGER = logging.getLogger(__name__)


class FoxifyFundedFetcher(FoxifyFetcher):
    """Foxify funded exchange fetcher."""

    def __init__(
        self,
        pair_map: dict[str, str],
        web3_address: ChecksumAddress,
        message_bus: ExchangeFetcherMessageBus,
    ) -> None:
        """Initialize shared attributes.

        Args:
            pair_map (dict[str, dict[str, str]]): Dict with adress and pair.
            web3_address (ChecksumAddress): Web3 account address.
            message_bus (ExchangeFetcherMessageBus): Message bus.
        """
        super().__init__(pair_map, web3_address, message_bus)
        self._funded_trader_contract = foxify_utils.build_funded_trader_contract(
            web3_address,
            self.web3_provider,
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=5),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_stable_balance(self) -> Decimal:
        """Fetch stable balance.

        Returns:
            Decimal: Balance in USD Stable Format.
        """
        balance = await self._funded_trader_contract.functions.balance().call()

        return Decimal(balance) / 10**foxify_utils.USDC_DECIMAL_PLACES
