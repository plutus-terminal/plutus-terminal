"""Class to encrypt and decrypt passwords."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import keyring
from qasync import os

from plutus_terminal.core.config import CONFIG
from plutus_terminal.core.exceptions import (
    InvalidPasswordError,
    KeyringPasswordNotFoundError,
)

if TYPE_CHECKING:
    from plutus_terminal.core.db.models import KeyringAccount


class PasswordGuard:
    """Class to encrypt and decrypt passwords."""

    def __init__(self) -> None:
        """Initialize widget."""
        self._password = ""
        self._validation_text = "Validate Password Check@"

    @property
    def password(self) -> str:
        """Get password."""
        return self._password

    @password.setter
    def password(self, password: str) -> None:
        """Set password."""
        self._password = password
        if CONFIG.get_gui_settings("first_run"):
            CONFIG.set_gui_settings("password_validation", self.encrypt(self._validation_text))
            CONFIG.set_gui_settings("first_run", False)
        elif not self.validate_password():
            raise InvalidPasswordError

    def encrypt(self, private_data: str) -> str:
        """Encrypt password.

        Add 16 random bytes to password before encrypting.

        Args:
            private_data (str): Private data being encrypted.

        Returns:
            bytes: Salt + Encrypted password.
        """
        salt = os.urandom(16)
        cryptographic_key = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(cryptographic_key.derive(self._password.encode()))
        cipher = Fernet(key)
        encrypted_data = salt + cipher.encrypt(private_data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt password.

        Args:
            encrypted_data (str): Encrypted password.
            salt (bytes): Salt.

        Returns:
            str: Decrypted password.
        """
        encrypted_data_bytes = base64.urlsafe_b64decode(encrypted_data)

        salt = encrypted_data_bytes[:16]
        encrypted_data_bytes = encrypted_data_bytes[16:]
        cryptographic_key = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(cryptographic_key.derive(self._password.encode()))
        cipher = Fernet(key)
        return cipher.decrypt(encrypted_data_bytes).decode()

    def validate_password(self) -> bool:
        """Validate password."""
        encrypted_validation = CONFIG.get_gui_settings("password_validation")
        if not encrypted_validation:
            return False
        try:
            decrypted_validation = self.decrypt(encrypted_validation)
        except InvalidToken:
            return False
        return decrypted_validation == self._validation_text

    def get_keyring_password(self, keyring_account: KeyringAccount) -> str:
        """Get keyring password."""
        encrypted_keyring_password = keyring.get_password(
            "plutus-terminal",
            str(keyring_account.username),
        )
        if encrypted_keyring_password is None:
            msg = "Keyring password not found"
            raise KeyringPasswordNotFoundError(msg)

        return self.decrypt(encrypted_keyring_password)
