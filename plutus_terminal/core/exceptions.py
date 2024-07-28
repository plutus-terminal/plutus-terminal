"""Custom exceptions."""


class OptionsNotAvailableError(Exception):
    """Error raise when Options is not availabe on exchange."""


class TransactionFailedError(Exception):
    """Error raise when transaction failed."""


class KeyringPasswordNotFoundError(Exception):
    """Error raise when password not found in keyring."""
