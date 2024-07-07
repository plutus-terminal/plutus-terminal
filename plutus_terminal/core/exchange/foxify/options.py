"""Foxify exchange options."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import TYPE_CHECKING, Self

from httpx import AsyncClient, Client, ConnectError, HTTPStatusError, ReadTimeout
import pandas
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.exceptions import ContractLogicError
from web3.types import Gwei, Nonce, Wei

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import TransactionFailedError
from plutus_terminal.core.exchange.base import ExchangeOptions
from plutus_terminal.core.exchange.foxify import utils as foxify_utils
from plutus_terminal.core.exchange.web3 import web3_utils
from plutus_terminal.core.types_ import (
    OptionsBuyParams,
    OptionsDirection,
    OptionsOrdersParams,
    OptionsPercent,
    OptionsRisk,
    OptionsSortingBy,
    OptionsStrategy,
)
from plutus_terminal.log_utils import log_retry

if TYPE_CHECKING:
    from decimal import Decimal

    from eth_account.signers.local import LocalAccount


LOGGER = logging.getLogger(__name__)


class FoxifyOptions(ExchangeOptions):
    """Handle Options on Foxify Exchange."""

    def __init__(self, web3_account: LocalAccount, extra_gas: Gwei) -> None:
        """Initialize shared attributes.

        Args:
            web3_account (LocalAccount): Web3 Account.
            extra_gas (Gwei): Extra gas for all transactions.
        """
        self.web3_account = web3_account
        self.extra_gas = extra_gas
        self.web3_provider = AsyncWeb3(
            AsyncHTTPProvider(str(CONFIG.get_web3_rpc_by_name("Arbitrum One").rpc_url)),
        )
        self.core_contract = foxify_utils.build_options_core_contract(
            self.web3_provider,
        )

    @classmethod
    async def create(cls, web3_account: LocalAccount, extra_gas: Gwei) -> Self:
        """Create class instance and init_async.

        Args:
            web3_account (LocalAccount): Web3 Account.
            extra_gas (Gwei): Extra gas for all transactions.

        Returns:
            FoxifyOptions: Instance of FoxifyOptions.
        """
        return cls(web3_account, extra_gas)

    async def fetch_orders(
        self,
        options_orders_params: OptionsOrdersParams,
    ) -> pandas.DataFrame:
        """Fetch options orders based on parameters.

        Args:
            options_orders_params (OrdersParams): Params for request.

        Returns:
            pandas.DataFrame: DataFrame with options orders.
        """
        request_url = "https://api-options.prd.foxify.trade/api/orders"
        async with AsyncClient() as client:
            response = await client.get(
                request_url,
                params=options_orders_params,  # type: ignore
            )
        response.raise_for_status()

        data = pandas.DataFrame(response.json())
        data["id"] = data["id"].astype(int)
        data["orderId"] = data["orderId"].astype(int)
        data["amount"] = data["amount"].astype("int64")
        data["reserved"] = data["reserved"].astype("int64")
        data["available"] = data["available"].astype("int64")
        data["percent"] = data["percent"].astype("int64")
        data["rate"] = data["rate"].astype("int64")
        data["duration"] = data["duration"].astype("int64")
        return data

    @retry(
        retry=(
            retry_if_exception_type(HTTPStatusError)
            | retry_if_exception_type(ReadTimeout)
            | retry_if_exception_type(ConnectError)
        ),
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def fetch_latest_vaa(self, price_feed_id: str) -> str:
        """Fetch the latest price vaa from Pyth using Hermes.

        Args:
            price_feed_id (str): Price feed ID to fetch vaa.

        Returns:
            str: VVA for the price.

        Raises:
            HTTPStatusError: If response is not successful. After tries.
        """
        request_url = "https://hermes.pyth.network/api/latest_vaas"
        request_params = {"ids[]": [price_feed_id]}

        async with AsyncClient() as client:
            response = await client.get(request_url, params=request_params)
        response.raise_for_status()

        data = response.json()
        return "0x" + binascii.hexlify(base64.b64decode(data[0])).decode("ascii")

    @retry(
        retry=(
            retry_if_exception_type(HTTPStatusError)
            | retry_if_exception_type(ReadTimeout)
            | retry_if_exception_type(ConnectError)
        ),
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=0.15, max=1),
        before_sleep=before_sleep_log(LOGGER, logging.DEBUG),
        retry_error_callback=log_retry(LOGGER),
    )
    async def _notify_api_options_bought(self, tx_hash: str) -> None:
        """Notify API that an order was bought.

        Args:
            tx_hash (str): Tx hash to notify.
        """
        request_url = "https://api-options.prd.foxify.trade/api/positions/accept"
        request_params = {"txHash": tx_hash}

        async with AsyncClient() as client:
            response = await client.post(request_url, json=request_params)
        response.raise_for_status()

    async def approve_stable(self) -> None:
        """Approve stable."""
        await foxify_utils.approve_stable(
            self.web3_provider,
            self.core_contract,
            self.web3_account,
        )

    async def buy_options(self, options_buy_params: OptionsBuyParams) -> None:
        """Buy options.

        Args:
            options_buy_params (OptionsBuyParams): Params to buy options.

        Raises:
            TransactionError: If transaction fails.
        """
        nonce: Nonce = await self.web3_provider.eth.get_transaction_count(
            self.web3_account.address,
        )
        latest_vaa = await self.fetch_latest_vaa(options_buy_params["price_id"])
        data = []
        for order_id, amount in options_buy_params["orders"].items():
            data.append(
                {
                    "orderId": order_id,
                    "amount": amount,
                    "updateData": [latest_vaa],
                },
            )

        try:
            tx = await self.core_contract.functions.accept(
                self.web3_account.address,
                data,
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
        except (ContractLogicError, ValueError) as error:
            raise TransactionFailedError from error

        signed_tx = self.web3_account.sign_transaction(tx)
        send_txn = await self.web3_provider.eth.send_raw_transaction(
            signed_tx.rawTransaction,
        )
        await self.web3_provider.eth.wait_for_transaction_receipt(send_txn)
        await self._notify_api_options_bought(self.web3_provider.to_hex(send_txn))
        LOGGER.info(
            "Bought options tx: https://arbiscan.io/tx/%s",
            self.web3_provider.to_hex(send_txn),
        )

    def fetch_available_pairs(self) -> list[str]:
        """Fetch available pairs for options.

        Returns:
            list[str]: List of available pairs.
        """
        request_url = "https://api-options.prd.foxify.trade/api/oracles"

        with Client() as client:
            response = client.get(request_url)
        response.raise_for_status()
        data = response.json()

        return [entry["name"] for entry in data]

    async def filter_with_strategy(
        self,
        direction: OptionsDirection,
        value: Decimal,
        pair: str,
    ) -> pandas.DataFrame:
        """Filter options based on strategy.

        Args:
            direction (OptionsDirection): Direction to buy the option.
            value (Decimal): Max value to spend.
            pair (str): Pair to open options for.

        Returns:
            pandas.DataFrame: DataFrame with options orders.
        """
        # build strategy
        percent_prefix = "UP" if direction == OptionsDirection.UP else "DOWN"

        percent_min_key = f"{percent_prefix}_{CONFIG.options_percent_min.replace('.', '')[:-1]}"
        percent_max_key = f"{percent_prefix}_{CONFIG.options_percent_max.replace('.', '')[:-1]}"

        percent_min = OptionsPercent[
            percent_min_key if CONFIG.options_percent_min != "0%" else percent_prefix
        ]
        percent_max = OptionsPercent[
            percent_max_key if CONFIG.options_percent_max != "0%" else percent_prefix
        ]

        strategy = OptionsStrategy(
            {
                "direction": direction,
                "rate_min": CONFIG.options_rate_min,
                "available_min": CONFIG.options_available_min,
                "percent_min": percent_min,
                "percent_max": percent_max,
                "duration_min": CONFIG.options_duration_min,
                "duration_max": CONFIG.options_duration_max,
                "risk": CONFIG.options_risk,
            },
        )

        # fetch current orders
        options_params: OptionsOrdersParams = {
            "sorting_by": OptionsSortingBy.RATE,
            "closed": False,
        }
        orders_data = await self.fetch_orders(options_params)

        # Common filtering logic
        common_filter = (
            (orders_data["rate"] + (1 * 10**18) >= strategy["rate_min"] * 10**18)
            & (orders_data["available"] >= strategy["available_min"] * 10**6)
            & (orders_data["direction"] == str(strategy["direction"]))
            & (orders_data["duration"] >= strategy["duration_min"])
            & (orders_data["duration"] <= strategy["duration_max"])
            & (orders_data["creator"] != self.web3_account.address.lower())
            & (orders_data["oracle"].apply(lambda x: x.get("name")) == pair)
        )

        # Direction-specific filtering
        if direction == OptionsDirection.UP:
            direction_filter = (orders_data["percent"] >= strategy["percent_min"]) & (
                orders_data["percent"] <= strategy["percent_max"]
            )

        else:
            direction_filter = (orders_data["percent"] <= strategy["percent_min"]) & (
                orders_data["percent"] >= strategy["percent_max"]
            )

        filtered_data = orders_data[common_filter & direction_filter]

        # Apply risk strategy to filtered order
        sort_by, ascending = [], []
        if strategy["risk"] == OptionsRisk.PRIO_RETURN:
            sort_by = ["rate", "available"]
            ascending = [False, False]
        elif strategy["risk"] == OptionsRisk.PRIO_SAFETY:
            sort_by = ["duration", "percent", "rate", "available"]
            ascending = [True, True, False, False]

        if sort_by:
            filtered_data = filtered_data.sort_values(by=sort_by, ascending=ascending)
        filtered_data = filtered_data.reset_index(drop=True)

        if filtered_data.empty:
            LOGGER.debug("No options to buy, based on strategy: %s", strategy)
            return pandas.DataFrame()

        # Process for target value
        filtered_data["cumulative_available"] = filtered_data["available"].cumsum()
        max_cumulative = filtered_data["cumulative_available"].iloc[-1]
        target_value = int(value.scaleb(6))
        target_sum = min(target_value, max_cumulative)

        last_index = (
            filtered_data[filtered_data["cumulative_available"] > target_sum].index[0]
            if target_value <= max_cumulative
            else filtered_data.index[-1]
        )
        return filtered_data.loc[:last_index]
