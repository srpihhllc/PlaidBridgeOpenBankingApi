# =============================================================================
# FILE: app/utils/plaid_crypto.py
# DESCRIPTION: Utility functions for encrypting and decrypting Plaid access tokens.
# =============================================================================

import os

from cryptography.fernet import Fernet


class PlaidCryptoError(Exception):
    """Custom exception for Plaid crypto operations."""

    pass


def _get_fernet() -> Fernet:
    """
    Retrieve the Fernet instance using the PLAID_ENCRYPTION_KEY from environment.
    The key must be a 32-byte URL-safe base64-encoded string.
    """
    key = os.getenv("PLAID_ENCRYPTION_KEY")
    if not key:
        raise PlaidCryptoError("PLAID_ENCRYPTION_KEY not set in environment.")
    try:
        return Fernet(key.encode())
    except Exception as e:
        raise PlaidCryptoError(f"Invalid PLAID_ENCRYPTION_KEY: {e}") from e


def encrypt_token(token: str) -> str:
    """
    Encrypt a Plaid access token using Fernet.
    Returns the encrypted token as a string.
    """
    f = _get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a Plaid access token using Fernet.
    Returns the plaintext token as a string.
    """
    f = _get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()
