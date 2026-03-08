"""Dict of valid exchanges."""

from plutus_terminal.core.exchange.foxify.exchange import FoxifyExchange
from plutus_terminal.core.exchange.foxify.funded_exchange import FoxifyFundedExchange
from plutus_terminal.core.exchange.orderly.exchange import OrderlyExchange

VALID_EXCHANGES = {
    "orderly": OrderlyExchange,
}
