"""Web3 utilities functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from web3.types import TxReceipt, Wei

from plutus_terminal.core.types_ import MessageLevel, UserMessage

if TYPE_CHECKING:
    import logging

    from hexbytes import HexBytes
    from web3 import AsyncWeb3
    from web3.types import Gwei, TxParams

    from plutus_terminal.message_bus import MessageBus


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
    message_bus: MessageBus,
    message_id: Optional[bytes] = None,
) -> TxReceipt:
    """Await transaction receipt and report result.

    Args:
        send_txn (HexBytes): Transaction hash.
        web3_provider (AsyncWeb3): Web3 provider.
        message (str): Message to display.
        scan_url (str): Scan url.
        log (logging.Logger): Log instance.
        message_bus (MessageBus): Message bus.
        message_id (Optional[bytes]): Message id.

    """
    user_message = UserMessage(
        text=f"Awaiting: {message}...",
        level=MessageLevel.WARNING,
        timeout_ms=5000,
        message_id=message_id,
    )
    message_bus.send_message.emit(user_message)

    tx_receipt = await web3_provider.eth.wait_for_transaction_receipt(send_txn)
    if tx_receipt["status"] == 1:
        log.info(
            "Transaction Sucessfully Sent: %s Tx: %s%s",
            message,
            scan_url,
            web3_provider.to_hex(send_txn),
        )

        user_message = (
            f"Sucessfull: {message} "
            f"<a href='{scan_url}{web3_provider.to_hex(send_txn)}'>TX Link</a>"
        )
        message_bus.send_message.emit(
            UserMessage(
                text=user_message,
                level=MessageLevel.SUCCESS,
                timeout_ms=5000,
                message_id=message_id,
            )
        )
    else:
        log.warning(
            "Transaction Failed: %s Tx: %s%s",
            message,
            scan_url,
            web3_provider.to_hex(send_txn),
        )
        user_message = (
            f"Failed: {message} <a href='{scan_url}{web3_provider.to_hex(send_txn)}'>TX Link</a>"
        )
        message_bus.send_message.emit(
            UserMessage(
                text=user_message,
                level=MessageLevel.ERROR,
                timeout_ms=5000,
                message_id=message_id,
            )
        )
    return tx_receipt
