"""Dict of valid exchanges."""

from plutus_terminal.core.exchange.foxify.exchange import FoxifyExchange
from plutus_terminal.core.exchange.foxify.funded_exchange import FoxifyFundedExchange

VALID_EXCHANGES = {"foxify": FoxifyExchange, "foxify_funded": FoxifyFundedExchange}
