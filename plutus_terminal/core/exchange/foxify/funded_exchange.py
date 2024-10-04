"""Foxify Funded Exchange."""

from decimal import Decimal

from qasync import asyncSlot
from web3 import Account, HTTPProvider, Web3
from web3.types import Gwei

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exchange.base import ExchangeFetcherMessageBus
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.foxify.exchange import FoxifyExchange
from plutus_terminal.core.exchange.foxify.funded_fetcher import FoxifyFundedFetcher
from plutus_terminal.core.exchange.foxify.funded_trader import FoxifyFundedTrader
from plutus_terminal.core.password_guard import PasswordGuard
from plutus_terminal.ui.widgets.toast import Toast, ToastType


class FoxifyFundedExchange(FoxifyExchange):
    """Foxify Funded Exchange."""

    def __init__(self, fetcher_bus: ExchangeFetcherMessageBus, pass_guard: PasswordGuard) -> None:
        """Initialize shared attributes.

        Args:
            fetcher_bus (ExchangeFetcherMessageBus): ExchangeFetcherMessageBus.
            pass_guard (PasswordGuard): PasswordGuard.
        """
        super().__init__(fetcher_bus=fetcher_bus, pass_guard=pass_guard)

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

        self._min_leverage = chanllenge_configs[11] / basis_point
        self._max_leverage = chanllenge_configs[12] / basis_point

        # If trader is on challenge get min deposit from min_deposit_stable
        # Otherwise get it from funding value
        if trader_challenge == 1:
            min_deposit_stable = chanllenge_configs[14] / 10**foxify_utils.USDC_DECIMAL_PLACES
        else:
            min_deposit_stable = chanllenge_configs[13] / 10**foxify_utils.USDC_DECIMAL_PLACES

        self._min_order_size = Decimal(chanllenge_configs[9] / basis_point) * Decimal(
            min_deposit_stable,
        )
        self._max_order_size = Decimal(chanllenge_configs[10] / basis_point) * Decimal(
            min_deposit_stable,
        )

        self._trader = await FoxifyFundedTrader.create(
            self._pair_map,
            self.web3_account,
            Gwei(0),
        )
        self._fetcher = await FoxifyFundedFetcher.create(
            self._pair_map,
            self._funded_trader_address,
            self.fetcher_bus,
        )

    @property
    def min_order_size(self) -> Decimal:
        """Return min trade size."""
        return self._min_order_size

    @property
    def max_order_size(self) -> Decimal:
        """Return max trade size."""
        return self._max_order_size

    @property
    def account_info(self) -> dict[str, str]:
        """Return info to be added to account info widget."""
        return {
            "Exchange": self.name().capitalize(),
            "Exchange Type": self.exchange_type().name,
            "Wallet": f"{self.web3_account.address[:5]}...{self.web3_account.address[-5:]}",
            "Trader Wallet": f"{self._funded_trader_address[:5]}...{self._funded_trader_address[-5:]}",  # noqa: E501
        }

    @asyncSlot()
    async def is_ready_to_trade(self) -> bool:
        """Check if contracts are approaved.

        Returns:
            bool: True if account is ready to trade.
        """
        # Funded contracts don't need to be approved
        return True

    @asyncSlot()
    async def set_all_leverage(self, leverage: int) -> None:
        """Set leverage for all positions.

        Args:
            leverage (int): Leverage to set.
        """
        toast_id = Toast.show_message(
            f"Leverage set to all pairs: {leverage}x",
            type_=ToastType.SUCCESS,
        )
        if leverage < self._min_leverage:
            Toast.update_message(
                toast_id,
                f"Leverage is too low. Set minimum leverage: {self._min_leverage}x",
                type_=ToastType.WARNING,
            )
            leverage = self._min_leverage
        elif leverage > self._max_leverage:
            Toast.update_message(
                toast_id,
                f"Leverage is too high. Set maximum leverage: {self._max_leverage}x",
                type_=ToastType.WARNING,
            )
            leverage = self._max_leverage

        CONFIG.leverage = leverage

    @asyncSlot()
    async def set_leverage(self, coin: str, leverage: int) -> None:
        """Set leverage for pair.

        Args:
            coin (str): Coin to set leverage for.
            leverage (int): Leverage to set.
        """
        pair = self.format_pair_from_coin(coin)
        toast_id = Toast.show_message(
            f"Leverage of {pair} set to: {leverage}x",
            type_=ToastType.SUCCESS,
        )
        if leverage < self._min_leverage:
            Toast.update_message(
                toast_id,
                f"Leverage of {pair} is too low. Set minimum leverage: {self._min_leverage}x",
                type_=ToastType.WARNING,
            )
            leverage = self._min_leverage
        elif leverage > self._max_leverage:
            Toast.update_message(
                toast_id,
                f"Leverage of {pair} is too high. Set maximum leverage: {self._max_leverage}x",
                type_=ToastType.WARNING,
            )
            leverage = self._max_leverage

        CONFIG.leverage = leverage

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
