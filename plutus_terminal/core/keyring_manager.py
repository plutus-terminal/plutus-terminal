"""Module to manage keyring."""

import keyring
import orjson

from plutus_terminal.core.config import AppConfig
from plutus_terminal.core.exceptions import KeyringPasswordNotFoundError
from plutus_terminal.core.password_guard import PasswordGuard


def get_exchange_password(account_name: str, pass_guard: PasswordGuard) -> list[str]:
    """Get exchange password from keyring.

    The password is stored as a json string decoded to utf-8.

    Args:
        account_name (str): Name of the account.
        pass_guard (PasswordGuard): Password guard.

    Returns:
        list[str]: List of secrets.

    Raises:
        KeyringPasswordNotFoundError: If password is not found in keyring.
    """
    encrypted_secrets = keyring.get_password(
        AppConfig.SERVICE_NAME,
        account_name,
    )
    if encrypted_secrets is None:
        msg = f"Exchange password not found for {account_name}"
        raise KeyringPasswordNotFoundError(msg)
    return orjson.loads(pass_guard.decrypt(encrypted_secrets).encode("utf-8"))


def set_exchange_password(account_name: str, secrets: list[str], pass_guard: PasswordGuard) -> None:
    """Set exchange password in keyring.

    The password is stored as a json string decoded to utf-8.

    Args:
        account_name (str): Name of the account.
        secrets (list[str]): List of secrets.
        pass_guard (PasswordGuard): Password guard.
    """
    encrypted_secrets = pass_guard.encrypt(
        orjson.dumps(secrets).decode("utf-8"),
    )
    keyring.set_password(
        AppConfig.SERVICE_NAME,
        account_name,
        encrypted_secrets,
    )


def get_news_source_api_key(news_source: str, pass_guard: PasswordGuard) -> str:
    """Get news source API key from keyring.

    Args:
        news_source (str): Name of the news source.
        pass_guard (PasswordGuard): Password guard.

    Returns:
        str: API key.

    Raises:
        KeyringPasswordNotFoundError: If API key is not found in keyring.
    """
    encrypted_api_key = keyring.get_password(
        f"{AppConfig.SERVICE_NAME}:news-source",
        news_source,
    )
    if encrypted_api_key is None or not encrypted_api_key:
        msg = f"News source API key not found for {news_source}"
        raise KeyringPasswordNotFoundError(msg)

    return pass_guard.decrypt(encrypted_api_key)


def set_news_source_api_key(news_source: str, api_key: str, pass_guard: PasswordGuard) -> None:
    """Set news source API key in keyring.

    Args:
        news_source (str): Name of the news source.
        api_key (str): API key.
        pass_guard (PasswordGuard): Password guard.
    """
    encrypted_api_key = pass_guard.encrypt(api_key)
    keyring.set_password(
        f"{AppConfig.SERVICE_NAME}:news-source",
        news_source,
        encrypted_api_key,
    )
