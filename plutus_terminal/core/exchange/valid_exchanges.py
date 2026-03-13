"""Dict of valid exchanges."""

from plutus_terminal.core.exchange.orderly.exchange import OrderlyExchange

VALID_EXCHANGES = {
    "orderly": OrderlyExchange,
}
