"""Utilities for foxify exchange."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict

from web3 import AsyncWeb3
from web3.types import Gwei, Nonce, TxParams, Wei

from plutus_terminal.core.exchange.web3 import web3_utils
from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    from decimal import Decimal

    from eth_account.signers.local import LocalAccount
    from eth_typing import ChecksumAddress
    from web3.contract.async_contract import AsyncContract

    from plutus_terminal.core.exchange.types import PerpsTradeType
    from plutus_terminal.core.types_ import PerpsTradeDirection

LOGGER = logging.getLogger(__name__)

REFERRAL_CODE = "0x706c757475735f7465726d696e616c0000000000000000000000000000000000"

STABLE_ADDRESS = AsyncWeb3.to_checksum_address(
    "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
)

FOXIFY_POSITION_ROUTER = AsyncWeb3.to_checksum_address(
    "0x444A707dF66B124c92E0B9cB86ceb359F2A570FD",
)

FOXIFY_VAULT = AsyncWeb3.to_checksum_address(
    "0xF45CD8739C80cD069D816bf5e60a79FE090CEe30",
)

FOXIFY_ROUTER = AsyncWeb3.to_checksum_address(
    "0xaFc9e58A663Da7eA472ECF31ee5514221B7268b6",
)

FOXIFY_REFERRAL_STORAGE = AsyncWeb3.to_checksum_address(
    "0x7564A44c916485D44822C9728e11d78B2de4C302",
)

FOXIFY_ORDER_BOOK = AsyncWeb3.to_checksum_address(
    "0x72f399b84dBC018AC35af8064501594704a765B9",
)

FOXIFY_ROUTER_CALLBACK = AsyncWeb3.to_checksum_address(
    "0xabDBacB016705D5647C0d9eea6990765DC045120",
)

FOXIFY_FUNDED_FACTORY = AsyncWeb3.to_checksum_address(
    "0x57B0421e3B2A7E18102223F2e1E052b9f8aD1eFB",
)

USDC_DECIMAL_PLACES = 6
MAX_SLIPPAGE = 0.005


class OpenTradingArgs(TypedDict):
    """Args for trading perps."""

    index_token: str
    amount_in: Decimal
    size_delta: Decimal
    trade_direction: PerpsTradeDirection
    acceptable_price: Decimal
    trade_type: PerpsTradeType
    take_profit: Decimal
    stop_loss: Decimal


class CloseTradingArgs(TypedDict):
    """Args for closing trading perps."""

    index_token: str
    size_delta: Decimal
    trade_direction: PerpsTradeDirection
    acceptable_price: Decimal


class ReduceTradingArgs(CloseTradingArgs):
    """Args for reducing trading perps."""

    trade_type: PerpsTradeType


class CancelOrderArgs(TypedDict):
    """Args for canceling order."""

    order_index: int
    reduce_only: bool


class EditOrderArgs(TypedDict):
    """Args for editing order."""

    order_index: int
    size_delta: Decimal
    acceptable_price: Decimal
    trigger_above_threshold: bool
    trade_type: PerpsTradeType


def build_vault_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build vault contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for vault
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_vault.json"),
    ) as f:
        vault_abi = json.load(f)

    return web3_provider.eth.contract(address=FOXIFY_VAULT, abi=vault_abi)


def build_referral_storage_contract(web3_provider: AsyncWeb3) -> AsyncContract:
    """Build referral contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for referral
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_referral_storage.json"),
    ) as f:
        referral_abi = json.load(f)

    return web3_provider.eth.contract(address=FOXIFY_REFERRAL_STORAGE, abi=referral_abi)


def build_position_router_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build position router contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for position router.
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_position_router.json"),
    ) as f:
        abi = json.load(f)

    return web3_provider.eth.contract(address=FOXIFY_POSITION_ROUTER, abi=abi)


def build_router_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build router contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for router.
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_router.json"),
    ) as f:
        abi = json.load(f)

    return web3_provider.eth.contract(address=FOXIFY_ROUTER, abi=abi)


def build_order_book_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build order book contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for order book.
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_order_book.json"),
    ) as f:
        abi = json.load(f)

    return web3_provider.eth.contract(address=FOXIFY_ORDER_BOOK, abi=abi)


def build_funded_factory_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build funded factory contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for order book.
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_funded_factory.json"),
    ) as f:
        abi = json.load(f)

    return web3_provider.eth.contract(address=FOXIFY_FUNDED_FACTORY, abi=abi)


def build_funded_trader_contract(
    trader_address: ChecksumAddress,
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build funded trader contract.

    Args:
        trader_address (ChecksumAddress): Trader address.
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for order book.
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_funded_trader.json"),
    ) as f:
        abi = json.load(f)

    return web3_provider.eth.contract(address=trader_address, abi=abi)


async def build_time_lock_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build time lock contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for time lock.
    """
    with Path.open(
        Path(__file__).parent.joinpath("abi/foxify_time_lock.json"),
    ) as f:
        abi = json.load(f)

    time_lock_address = await build_vault_contract(web3_provider).functions.owner().call()
    return web3_provider.eth.contract(address=time_lock_address, abi=abi)


def build_stable_contract(
    web3_provider: AsyncWeb3,
) -> AsyncContract:
    """Build Options core contract.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.

    Returns:
        AsyncContract: Contract for options core.
    """
    with Path.open(Path(__file__).parent.parent.joinpath("web3/abi/usdc.json")) as f:
        stable_abi = json.load(f)

    return web3_provider.eth.contract(address=STABLE_ADDRESS, abi=stable_abi)


async def is_plugin_approved(
    web3_provider: AsyncWeb3,
    plugin_address: ChecksumAddress,
    wallet_address: ChecksumAddress,
) -> bool:
    """Verify if token plugin is approved on router.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        plugin_address (ChecksumAddress): Plugin address.
        wallet_address (ChecksumAddress): Address to check for approval.

    Returns:
        bool: True if the token is already approved. False otherwise.
    """
    router_contract = build_router_contract(web3_provider)

    approved = await router_contract.functions.approvedPlugins(
        wallet_address,
        plugin_address,
    ).call()
    return bool(approved)


async def approve_plugin(
    web3_provider: AsyncWeb3,
    plugin_address: ChecksumAddress,
    web3_account: LocalAccount,
) -> None:
    """Approve plugin.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        plugin_address (ChecksumAddress): Plugin address.
        web3_account (LocalAccount): Web3 account.
    """
    if await is_plugin_approved(
        web3_provider,
        plugin_address,
        web3_account.address,
    ):
        return

    router_contract = build_router_contract(web3_provider)
    transaction_count: Nonce = await web3_provider.eth.get_transaction_count(
        web3_account.address,
    )

    transaction_params: TxParams = {
        "gas": Wei(400000),
        "from": web3_account.address,
        "nonce": transaction_count,
        "value": Wei(0),
    }

    approval_transaction = await router_contract.functions.approvePlugin(
        plugin_address,
    ).build_transaction(transaction_params)

    # Estimate gas for transaction with extra gas for speed
    approval_transaction.update(
        {"gas": await web3_utils.estimate_gas(web3_provider, approval_transaction)},
    )

    signed_txn = web3_account.sign_transaction(approval_transaction)
    txn = await web3_provider.eth.send_raw_transaction(signed_txn.rawTransaction)

    await web3_utils.await_receipt_and_report(
        txn,
        web3_provider,
        "Plugin approved.",
        "https://arbiscan.io/tx/",
        LOGGER,
    )


async def is_stable_approved(
    web3_provider: AsyncWeb3,
    spender_address: ChecksumAddress,
    wallet_address: ChecksumAddress,
) -> bool:
    """Verify is token spend is approved on wallet.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        spender_address (ChecksumAddress): Spender address.
        wallet_address (ChecksumAddress): Address to check allowance.

    Returns:
        bool: True if the token is already approved. False otherwise.
    """
    stable_contract = build_stable_contract(web3_provider)

    approved = await stable_contract.functions.allowance(
        wallet_address,
        spender_address,
    ).call()
    approved_quantity = await stable_contract.functions.balanceOf(wallet_address).call()
    if int(approved) <= int(approved_quantity):
        return False
    return True


async def approve_stable(
    web3_provider: AsyncWeb3,
    spender_address: ChecksumAddress,
    web3_account: LocalAccount,
) -> None:
    """Approve stable for spender.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        spender_address (ChecksumAddress): Spender address.
        web3_account (LocalAccount): Web3 account.
    """
    if await is_stable_approved(web3_provider, spender_address, web3_account.address):
        return
    stable_contract = build_stable_contract(web3_provider)
    transaction_count: Nonce = await web3_provider.eth.get_transaction_count(
        web3_account.address,
    )

    transaction_params: TxParams = {
        "gas": Wei(400000),
        "from": web3_account.address,
        "nonce": transaction_count,
        "value": Wei(0),
        "maxFeePerGas": await web3_utils.estimate_gas_price(web3_provider, Gwei(0)),
        "maxPriorityFeePerGas": web3_provider.to_wei(0, "gwei"),
    }
    max_approval = 115792089237316195423570985008687907853269984665640564039457584007913129639935
    approval_transaction = await stable_contract.functions.approve(
        spender_address,
        max_approval,
    ).build_transaction(transaction_params)

    # Estimate gas for transaction with extra gas for speed
    approval_transaction.update(
        {"gas": await web3_utils.estimate_gas(web3_provider, approval_transaction)},
    )

    signed_txn = web3_account.sign_transaction(approval_transaction)
    txn = await web3_provider.eth.send_raw_transaction(signed_txn.rawTransaction)

    await web3_utils.await_receipt_and_report(
        txn,
        web3_provider,
        "Stable approved.",
        "https://arbiscan.io/tx/",
        LOGGER,
    )


async def ensure_referral(
    web3_provider: AsyncWeb3,
    web3_account: LocalAccount,
) -> None:
    """Ensure referral is set.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        web3_account (LocalAccount): Web3 account.
    """
    referral_contract = build_referral_storage_contract(web3_provider)
    current_referral = web3_provider.to_hex(
        await referral_contract.functions.traderReferralCodes(
            web3_account.address,
        ).call(),
    )
    if current_referral == REFERRAL_CODE:
        return

    transaction_count: Nonce = await web3_provider.eth.get_transaction_count(
        web3_account.address,
    )

    transaction_params: TxParams = {
        "gas": Wei(400000),
        "from": web3_account.address,
        "nonce": transaction_count,
        "value": Wei(0),
        "maxFeePerGas": await web3_utils.estimate_gas_price(web3_provider, Gwei(0)),
        "maxPriorityFeePerGas": web3_provider.to_wei(0, "gwei"),
    }
    set_referral_trasaction = await referral_contract.functions.setTraderReferralCodeByUser(
        REFERRAL_CODE,
    ).build_transaction(transaction_params)
    # Estimate gas for transaction with extra gas for speed
    set_referral_trasaction.update(
        {"gas": await web3_utils.estimate_gas(web3_provider, set_referral_trasaction)},
    )
    signed_txn = web3_account.sign_transaction(set_referral_trasaction)
    txn = await web3_provider.eth.send_raw_transaction(signed_txn.rawTransaction)

    await web3_utils.await_receipt_and_report(
        txn,
        web3_provider,
        "Referral set.",
        "https://arbiscan.io/tx/",
        LOGGER,
    )
