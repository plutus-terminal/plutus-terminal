"""Web3 utilities functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from web3.types import TxReceipt, Wei

from plutus_terminal.ui.widgets.toast import Toast, ToastType

if TYPE_CHECKING:
    import logging

    from hexbytes import HexBytes
    from web3 import AsyncWeb3
    from web3.types import Gwei, TxParams


async def estimate_gas_price(web3_provider: AsyncWeb3, extra_gas: Gwei) -> Wei:
    """Estimate transaction gas price.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        extra_gas (Gwei): Extra gas.

    Returns:
        Wei: Estimated gas price.
    """
    block_data = await web3_provider.eth.get_block("pending")
    base_fee = block_data["baseFeePerGas"]  # type: ignore
    priority_fee = web3_provider.to_wei(extra_gas, "gwei")
    max_fee = (2 * base_fee) + priority_fee
    return Wei(max_fee)


async def estimate_gas(web3_provider: AsyncWeb3, transaction: TxParams) -> Wei:
    """Estimate amount of gas to use in the transaction.

    Args:
        web3_provider (AsyncWeb3): Web3 provider.
        transaction (TxParams): Transaction params.

    Returns:
        Wei: Estimated gas.
    """
    gas = await web3_provider.eth.estimate_gas(
        {
            "from": transaction["from"],
            "to": transaction["to"],
            "value": transaction["value"],
            "data": transaction["data"],
        },
    )
    gas = int(gas + (gas / 10))
    return Wei(gas)


async def await_receipt_and_report(
    send_txn: HexBytes,
    web3_provider: AsyncWeb3,
    message: str,
    scan_url: str,
    log: logging.Logger,
    toast_id: Optional[bytes] = None,
) -> TxReceipt:
    """Await transaction receipt and report result.

    Args:
        send_txn (HexBytes): Transaction hash.
        web3_provider (AsyncWeb3): Web3 provider.
        message (str): Message to display.
        scan_url (str): Scan url.
        log (logging.Logger): Log instance.
        toast_id (Optional[bytes]): Toast id. If none create one.

    """
    if toast_id is None:
        toast_id = Toast.show_message(
            message=f"Awaiting::{message}...",
            type_=ToastType.WARNING,
            timeout=5000,
        )
    else:
        Toast.update_message(
            toast_id,
            message=f"Awaiting::{message}...",
            type_=ToastType.WARNING,
        )
    tx_receipt = await web3_provider.eth.wait_for_transaction_receipt(send_txn)
    if tx_receipt["status"] == 1:
        log.info(
            "Transaction Sucessfully Sent:: %s Tx:: %s%s",
            message,
            scan_url,
            web3_provider.to_hex(send_txn),
        )
        toast_message = (
            f"Sucessfull::{message} "
            f"<a href='{scan_url}{web3_provider.to_hex(send_txn)}'>TX Link</a>"
        )
        Toast.update_message(
            toast_id,
            message=toast_message,
            type_=ToastType.SUCCESS,
        )
    else:
        log.warning(
            "Transaction Failed:: %s Tx:: %s%s",
            message,
            scan_url,
            web3_provider.to_hex(send_txn),
        )
        toast_message = (
            f"Failed::{message} "
            f"<a href='{scan_url}{web3_provider.to_hex(send_txn)}'>TX Link</a>"
        )
        Toast.update_message(
            toast_id,
            message=toast_message,
            type_=ToastType.ERROR,
        )
    return tx_receipt
