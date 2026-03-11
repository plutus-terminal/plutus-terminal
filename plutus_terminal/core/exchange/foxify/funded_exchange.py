"""Foxify Funded Exchange."""

from decimal import Decimal

from qasync import asyncSlot
from web3 import Account, HTTPProvider, Web3
from web3.types import Gwei

from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.foxify.exchange import FoxifyExchange
from plutus_terminal.core.exchange.foxify.funded_fetcher import FoxifyFundedFetcher
from plutus_terminal.core.exchange.foxify.funded_trader import FoxifyFundedTrader
from plutus_terminal.core.password_guard import PasswordGuard
from plutus_terminal.message_bus import MessageBus


class FoxifyFundedExchange(FoxifyExchange):
    """Foxify Funded Exchange."""

    def __init__(
        self,
        message_bus: MessageBus,
        pass_guard: PasswordGuard,
        app_config: AppConfig,
    ) -> None:
        """Initialize shared attributes.

        Args:
            message_bus (MessageBus): Message bus to send signals.
            pass_guard (PasswordGuard): PasswordGuard.
            app_config (AppConfig): App config.
        """
        super().__init__(message_bus=message_bus, pass_guard=pass_guard, app_config=app_config)

    async def init_async(self) -> None:
        """Initialize async shared attributes."""
        self._funded_factory_contract = foxify_utils.build_funded_factory_contract(
            self.web3_provider,
        )

        self._funded_trader_address = self.web3_provider.to_checksum_address(
            await self._funded_factory_contract.functions.traderContracts(
                self.web3_account.address,
            ).call(),
        )

        self._funded_trader_contract = foxify_utils.build_funded_trader_contract(
            self._funded_trader_address,
            self.web3_provider,
        )

        basis_point = await self._funded_trader_contract.functions.BASIS_POINTS().call()
        trader_challenge = await self._funded_trader_contract.functions.traderChallenge().call()
        chanllenge_configs = await self._funded_factory_contract.functions.traderChallengeConfigs(
            trader_challenge,
        ).call()

        # Calculate min and max leverage
        self._min_leverage = chanllenge_configs[11] / basis_point
        self._max_leverage = chanllenge_configs[12] / basis_point

        # Calculate min and max order size
        trader_starting_capital = (
            await self._funded_trader_contract.functions.startingCapital().call()
            / 10**foxify_utils.USDC_DECIMAL_PLACES
        )

        self._min_order_size = Decimal(chanllenge_configs[9] / basis_point) * Decimal(
            trader_starting_capital,
        )
        self._max_order_size = Decimal(chanllenge_configs[10] / basis_point) * Decimal(
            trader_starting_capital,
        )

        self._trader = await FoxifyFundedTrader.create(
            self._pair_map,
            self.web3_account,
            Gwei(0),
        )
        self._fetcher = await FoxifyFundedFetcher.create(
            self._pair_map,
            self._funded_trader_address,
            self.message_bus,
        )

    @property
    def min_leverage(self) -> int:
        """Return min leverage."""
        return int(self._min_leverage)

    @property
    def max_leverage(self) -> int:
        """Return max leverage."""
        return int(self._max_leverage)

    @property
    def min_order_size(self) -> Decimal:
        """Return min trade size."""
        return self._min_order_size

    @property
    def max_order_size(self) -> Decimal:
        """Return max trade size."""
        return self._max_order_size

    @property
    def account_info(self) -> dict[str, object]:
        """Return info to be added to account info widget."""
        return {
            "Exchange": self.name().capitalize(),
            "Exchange Type": self.exchange_type().name,
            "Wallet": f"{self.web3_account.address[:5]}...{self.web3_account.address[-5:]}",
            "Trader Wallet": f"{self._funded_trader_address[:5]}...{self._funded_trader_address[-5:]}",
        }

    @asyncSlot()
    async def is_ready_to_trade(self) -> bool:
        """Check if contracts are approaved.

        Returns:
            bool: True if account is ready to trade.
        """
        # Funded contracts don't need to be approved
        return True

    @staticmethod
    def name() -> str:
        """Return exchange name."""
        return "foxify-FUNDED"

    @staticmethod
    def validate_secrets(secrets: list[str]) -> tuple[bool, str]:
        """Validate private key and Funded Trader Contract."""
        try:
            account = Account.from_key(secrets[0])
        except ValueError:
            return False, "Private key is invalid."

        web3_provider = Web3(HTTPProvider("https://arb1.arbitrum.io/rpc"))
        funded_factory_contract = foxify_utils.build_funded_factory_contract(
            web3_provider,  # type: ignore
        )
        trader_address = funded_factory_contract.functions.traderContracts(
            account.address,
        ).call()
        if trader_address == "0x0000000000000000000000000000000000000000":
            return False, "No associated Trader with given private key."

        return True, "Valid private key and Funded Trader Contract."
