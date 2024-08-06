"""Web3 Provider that cicles between mutiple providers to avoid rate limiting."""

import asyncio
import itertools
import logging
from typing import Any

from aiohttp import ClientResponseError
import orjson
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.providers.async_base import AsyncJSONBaseProvider
from web3.types import RPCEndpoint, RPCResponse

from plutus_terminal.core.config import CONFIG

LOGGER = logging.getLogger(__name__)


class AsyncCycleWeb3Provider(AsyncJSONBaseProvider):
    """Web3 Provider that cicles between mutiple providers to avoid rate limiting."""

    def __init__(self, providers: list[AsyncHTTPProvider]) -> None:
        """Initialize web3 provider.

        Args:
            providers (list[AsyncWeb3]): Web3 providers.
        """
        self._providers = providers
        self._providers_cycle = itertools.cycle(providers)
        self._lock = asyncio.Lock()
        super().__init__()

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:  # noqa: ANN401
        """Make request to provider.

        Args:
            method (str): Method to call.
            params (list): Params to pass.

        Returns:
            dict: Response.
        """
        async with self._lock:
            provider = next(self._providers_cycle)
        try:
            result = await provider.make_request(method, params)
        except ClientResponseError:
            LOGGER.warning("Provider %s is not available. Removing it...", provider)
            async with self._lock:
                self._providers.remove(provider)
                self._providers_cycle = itertools.cycle(self._providers)
            return await self.make_request(method, params)

        return result


def build_cycle_provider(chain_name: str) -> AsyncWeb3:
    """Build cycle web3 provider using Web3RPC from database.

    Args:
        chain_name (str): Chain name.

    Returns:
        AsyncCycleWeb3Provider: Web3 provider.
    """
    providers_urls = orjson.loads(str(CONFIG.get_web3_rpc_by_name(chain_name).rpc_urls))
    providers = [AsyncHTTPProvider(url) for url in providers_urls]

    provider = AsyncCycleWeb3Provider(providers)

    return AsyncWeb3(provider)
