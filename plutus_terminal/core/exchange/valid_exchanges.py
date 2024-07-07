"""Dict of valid exchanges."""

from plutus_terminal.core.exchange.bitget.exchange import BitgetExchange
from plutus_terminal.core.exchange.foxify.exchange import FoxifyExchange

VALID_EXCHANGES = {"foxify": FoxifyExchange}
