"""Custom exceptions."""


class OptionsNotAvailableError(Exception):
    """Error raise when Options is not availabe on exchange."""


class TransactionFailedError(Exception):
    """Error raise when transaction failed."""
