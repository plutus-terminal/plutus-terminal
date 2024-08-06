"""Foxify Exchange trader."""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
from typing import TYPE_CHECKING, Self

from tenacity import before_sleep_log, retry, wait_exponential
from web3.exceptions import ContractLogicError
from web3.types import Gwei, Nonce, Wei

from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.base import ExchangeTrader
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.types import (
    PerpsTradeDirection,
    PerpsTradeType,
    TradeResults,
)
from plutus_terminal.core.exchange.web3 import web3_utils
from plutus_terminal.core.exchange.web3.cycle_provider import build_cycle_provider
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from eth_account.signers.local import LocalAccount


LOGGER = logging.getLogger(__name__)


class FoxifyTrader(ExchangeTrader):
    """Handle trades on Foxify Exchange."""

    def __init__(
        self,
        pair_map: dict[str, str],
        web3_account: LocalAccount,
        extra_gas: Gwei,
    ) -> None:
        """Initialize shared attributes."""
        LOGGER.info("Initialize FoxifyTrader")
        LOGGER.debug("Using web3_account: %s", web3_account)
        LOGGER.debug("Extra gas: %s", extra_gas)
        self.pair_map = pair_map
        self.web3_account = web3_account
        self.extra_gas = extra_gas
        self._receiver_address = web3_account.address
        self.web3_provider = build_cycle_provider("Arbitrum One Trader")
        self._vault_contract = foxify_utils.build_vault_contract(self.web3_provider)
        self._position_router_contract = foxify_utils.build_position_router_contract(
            self.web3_provider,
        )
        self._order_book_contract = foxify_utils.build_order_book_contract(
            self.web3_provider,
        )

    @classmethod
    async def create(
        cls,
        pair_map: dict[str, str],
        web3_account: LocalAccount,
        extra_gas: Gwei,
    ) -> Self:
        """Create class instance and init_async.

        Args:
            pair_map (dict[str, str]): Dict with adress and pair.
            web3_account (LocalAccount): Web3 Account.
            extra_gas (Gwei): Extra gas for all transactions.

        Returns:
            FoxifyTrader: Instance of FoxifyTrader.
        """
        trader = cls(pair_map, web3_account, extra_gas)
        await trader.init_async()
        return trader

    @retry(
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def init_async(self) -> None:
        """Init async shared attributes."""
        (
            self._price_precision,
            self._position_execution_fee,
            self._order_execution_fee,
        ) = await asyncio.gather(
            self._vault_contract.functions.PRICE_PRECISION().call(),
            self._position_router_contract.functions.minExecutionFee().call(),
            self._order_book_contract.functions.minExecutionFee().call(),
        )

    async def approve_stable(self) -> None:
        """Approve stable token."""

    async def create_order(
        self,
        trade_arguments: foxify_utils.OpenTradingArgs,
    ) -> TradeResults:
        """Create new order.

        Args:
            trade_arguments (foxify.utils.OpenTradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.
            NotImplementedError: If the trade direction is not supported.

        Returns:
            TradeResults: Result of the trade.
        """
        LOGGER.info("Opening new position: %s", trade_arguments)
        if trade_arguments["trade_type"] == PerpsTradeType.MARKET:
            return await self._create_market_order(trade_arguments)
        if trade_arguments["trade_type"] == PerpsTradeType.LIMIT:
            return await self._create_limit_order(trade_arguments)
        msg = f"Not supported {trade_arguments['trade_type']}"
        raise NotImplementedError(msg)

    async def _create_market_order(
        self,
        trade_arguments: foxify_utils.OpenTradingArgs,
    ) -> TradeResults:
        """Create a market order.

        Args:
            trade_arguments (foxify.utils.OpenTradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )

        amount_in = int(trade_arguments["amount_in"] * 10**foxify_utils.USDC_DECIMAL_PLACES)
        size_delta = int(trade_arguments["size_delta"] * self._price_precision)
        stop_loss = int(trade_arguments["stop_loss"] * self._price_precision)
        take_profit = int(trade_arguments["take_profit"] * self._price_precision)
        price_bellow = (
            stop_loss
            if trade_arguments["trade_direction"] == PerpsTradeDirection.LONG
            else take_profit
        )
        price_above = (
            take_profit
            if trade_arguments["trade_direction"] == PerpsTradeDirection.LONG
            else stop_loss
        )

        order_execution_data = self.web3_provider.codec.encode(
            types=[
                "address",
                "uint256",
                "uint256",
                "uint256",
                "uint256",
                "uint256",
                "uint256",
                "bool",
            ],
            args=[
                self.web3_provider.to_checksum_address(trade_arguments["index_token"]),
                size_delta if trade_arguments["stop_loss"] != Decimal(0) else 0,
                size_delta if trade_arguments["take_profit"] != Decimal(0) else 0,
                amount_in,
                amount_in,
                price_bellow,
                price_above,
                trade_arguments["trade_direction"].value,
            ],
        )

        try:
            tx = await self._position_router_contract.functions.createIncreasePosition(
                self.web3_provider.to_checksum_address(trade_arguments["index_token"]),
                amount_in,
                0,  # minOut
                size_delta,
                trade_arguments["trade_direction"].value,
                int(trade_arguments["acceptable_price"] * self._price_precision),
                self._position_execution_fee,
                foxify_utils.REFERRAL_CODE,
                order_execution_data,
                foxify_utils.FOXIFY_ROUTER_CALLBACK,
            ).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                    "value": self._position_execution_fee,
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error

    async def _create_limit_order(
        self,
        trade_arguments: foxify_utils.OpenTradingArgs,
    ) -> TradeResults:
        """Create a limit order.

        Args:
            trade_arguments (foxify.utils.OpenTradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.
            NotImplementedError: If the trade direction is not supported.

        Returns:
            TradeResults: Result of the trade.
        """
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )
        try:
            tx = await self._order_book_contract.functions.createIncreaseOrder(
                int(
                    trade_arguments["amount_in"] * 10**foxify_utils.USDC_DECIMAL_PLACES,
                ),
                self.web3_provider.to_checksum_address(trade_arguments["index_token"]),
                int(trade_arguments["size_delta"] * self._price_precision),
                trade_arguments["trade_direction"].value,
                int(
                    trade_arguments["acceptable_price"] * self._price_precision,
                ),  # triggerPrice
                not trade_arguments["trade_direction"].value,
                self._order_execution_fee,
            ).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                    "value": self._order_execution_fee,
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error

    async def create_reduce_order(
        self,
        trade_arguments: foxify_utils.ReduceTradingArgs,
    ) -> TradeResults:
        """Create new reduce only order.

        Args:
            trade_arguments (foxify.utils.OpenTradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.
            NotImplementedError: If the trade direction is not supported.

        Returns:
            TradeResults: Result of the trade.
        """
        if trade_arguments["trade_type"] == PerpsTradeType.MARKET:
            return await self.close_position(trade_arguments)
        if trade_arguments["trade_type"] in (
            PerpsTradeType.TRIGGER_TP,
            PerpsTradeType.TRIGGER_SL,
        ):
            return await self._create_reduce_trigger_order(trade_arguments)
        msg = f"Not supported {trade_arguments['trade_type']}"
        raise NotImplementedError(msg)

    async def _create_reduce_trigger_order(
        self,
        trade_arguments: foxify_utils.ReduceTradingArgs,
    ) -> TradeResults:
        """Create a reduce only trigger order.

        Args:
            trade_arguments (foxify.utils.ReduceTradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.
            NotImplementedError: If the trade direction is not supported.

        Returns:
            TradeResults: Result of the trade.
        """
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )

        if trade_arguments["trade_type"] is PerpsTradeType.TRIGGER_SL:
            if trade_arguments["trade_direction"] is PerpsTradeDirection.LONG:
                trigger_above_price = False
            else:
                trigger_above_price = True
        elif trade_arguments["trade_type"] is PerpsTradeType.TRIGGER_TP:
            if trade_arguments["trade_direction"] is PerpsTradeDirection.LONG:
                trigger_above_price = True
            else:
                trigger_above_price = False
        else:
            msg = f"Not supported {trade_arguments['trade_type']}"
            raise NotImplementedError(msg)

        try:
            tx = await self._order_book_contract.functions.createDecreaseOrder(
                self.web3_provider.to_checksum_address(trade_arguments["index_token"]),
                int(trade_arguments["size_delta"] * self._price_precision),
                0,
                trade_arguments["trade_direction"].value,
                int(
                    trade_arguments["acceptable_price"] * self._price_precision,
                ),  # triggerPrice
                trigger_above_price,
            ).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                    "value": self._order_execution_fee + 1,
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error

    async def close_position(
        self,
        trade_arguments: foxify_utils.CloseTradingArgs,
    ) -> TradeResults:
        """Close the give position.

        Args:
            trade_arguments (foxify.utils.CloseTradingArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.
        """
        LOGGER.info("Closing position: %s", trade_arguments)
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )
        try:
            tx = await self._position_router_contract.functions.createDecreasePosition(
                self.web3_provider.to_checksum_address(trade_arguments["index_token"]),
                0,  # collateralDelta
                int(trade_arguments["size_delta"] * self._price_precision),
                trade_arguments["trade_direction"].value,
                self._receiver_address,
                int(trade_arguments["acceptable_price"] * self._price_precision),
                0,
                self._position_execution_fee,
                "0x0000000000000000000000000000000000000000",
            ).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                    "value": self._position_execution_fee,
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error

    async def cancel_order(
        self,
        trade_arguments: foxify_utils.CancelOrderArgs,
    ) -> TradeResults:
        """Cancel the given order.

        Args:
            trade_arguments (foxify.utils.CacelOrderArgs): Order to be close.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        LOGGER.info("Canceling order: %s", trade_arguments)
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )
        function_name = (
            "cancelDecreaseOrder" if trade_arguments["reduce_only"] else "cancelIncreaseOrder"
        )
        func = self._order_book_contract.get_function_by_name(function_name)
        try:
            tx = await func(trade_arguments["order_index"]).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error

    async def edit_order(
        self,
        trade_arguments: foxify_utils.EditOrderArgs,
    ) -> TradeResults:
        """Update the given order.

        Args:
            trade_arguments (EditOrderArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        if trade_arguments["trade_type"] == PerpsTradeType.LIMIT:
            return await self._edit_limit_order(trade_arguments)
        if trade_arguments["trade_type"] in (
            PerpsTradeType.TRIGGER_TP,
            PerpsTradeType.TRIGGER_SL,
        ):
            return await self._edit_trigger_order(trade_arguments)
        msg = f"Not supported {trade_arguments['trade_type']}"
        raise NotImplementedError(msg)

    async def _edit_limit_order(self, trade_arguments: foxify_utils.EditOrderArgs) -> TradeResults:
        """Edit a limit order.

        Args:
            trade_arguments (foxify.utils.EditOrderArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        LOGGER.info("Editing order: %s", trade_arguments)
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )
        try:
            tx = await self._order_book_contract.functions.updateIncreaseOrder(
                int(trade_arguments["order_index"]),
                int(trade_arguments["size_delta"] * self._price_precision),
                int(trade_arguments["acceptable_price"] * self._price_precision),
                trade_arguments["trigger_above_threshold"],
            ).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error

    async def _edit_trigger_order(
        self,
        trade_arguments: foxify_utils.EditOrderArgs,
    ) -> TradeResults:
        """Edit a trigger order.

        Args:
            trade_arguments (foxify.utils.EditOrderArgs): Arguments necessary for the trade.

        Raises:
            TransactionFailed: If the transaction fails.

        Returns:
            TradeResults: Result of the trade.
        """
        LOGGER.info("Editing order: %s", trade_arguments)
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )
        try:
            tx = await self._order_book_contract.functions.updateDecreaseOrder(
                int(trade_arguments["order_index"]),
                0,
                int(trade_arguments["size_delta"] * self._price_precision),
                int(trade_arguments["acceptable_price"] * self._price_precision),
                trade_arguments["trigger_above_threshold"],
            ).build_transaction(
                {
                    "nonce": nonce,
                    "from": self.web3_account.address,
                    "maxFeePerGas": await web3_utils.estimate_gas_price(
                        self.web3_provider,
                        self.extra_gas,
                    ),
                    "maxPriorityFeePerGas": self.web3_provider.to_wei(
                        self.extra_gas,
                        "gwei",
                    ),
                    "gas": Wei(1000000),
                },
            )
            tx.update({"gas": await web3_utils.estimate_gas(self.web3_provider, tx)})
            signed_tx = self.web3_account.sign_transaction(tx)
            return await self.web3_provider.eth.send_raw_transaction(
                signed_tx.rawTransaction,
            )
        except (ContractLogicError, ValueError, TypeError) as error:
            LOGGER.exception("Transaction failed")
            raise TransactionFailedError from error
