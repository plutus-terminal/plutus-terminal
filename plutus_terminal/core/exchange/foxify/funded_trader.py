"""Foxify Funded Exchange trader."""

from eth_account.signers.local import LocalAccount
from qasync import logging
from tenacity import before_sleep_log, retry, wait_exponential
from web3.types import Gwei

from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.foxify.trader import FoxifyTrader
from plutus_terminal.log_utils import log_retry

LOGGER = logging.getLogger(__name__)


class FoxifyFundedTrader(FoxifyTrader):
    """Foxify Funded Exchange trader."""

    def __init__(
        self,
        pair_map: dict[str, str],
        web3_account: LocalAccount,
        extra_gas: Gwei,
    ) -> None:
        """Initialize shared attributes."""
        super().__init__(pair_map, web3_account, extra_gas)

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def init_async(self) -> None:
        """Init async shared attributes."""
        await super().init_async()

        funded_factory_contract = foxify_utils.build_funded_factory_contract(
            self.web3_provider,
        )

        self._funded_trader_address = self.web3_provider.to_checksum_address(
            await funded_factory_contract.functions.traderContracts(
                self.web3_account.address,
            ).call(),
        )

        self._funded_trader_contract = foxify_utils.build_funded_trader_contract(
            self._funded_trader_address,
            self.web3_provider,
        )

        # Override position router and order book to point to trader contract
        self._position_router_contract = self._funded_trader_contract
        self._order_book_contract = self._funded_trader_contract

        # override receiver address
        self._receiver_address = self._funded_trader_address
