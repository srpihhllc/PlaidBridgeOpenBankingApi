# =============================================================================
# FILE: app/utils/plaid_crypto.py
# DESCRIPTION: Fail-closed encryption, decryption, and MultiFernet key rotation
#              for Plaid access tokens.
# =============================================================================

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class PlaidCryptoError(Exception):
    """Base exception for Plaid cryptographic failures."""


class PlaidKeyConfigurationError(PlaidCryptoError):
    """Raised when Plaid encryption key configuration is missing or invalid."""


class PlaidTokenDecryptionError(PlaidCryptoError):
    """Raised when a Plaid token cannot be decrypted or rotated."""


def _parse_plaid_key_ring() -> list[bytes]:
    """
    Build an ordered list of Fernet keys (primary key first for encryption,
    followed by fallback/previous keys for decryption and rotation).
    """
    keys: list[bytes] = []
    seen: set[bytes] = set()

    primary = (os.getenv("PLAID_ENCRYPTION_KEY") or "").strip().strip("'\"")
    if primary:
        encoded = primary.encode("utf-8")
        keys.append(encoded)
        seen.add(encoded)

    for env_var in ("PLAID_ENCRYPTION_KEYS", "PLAID_PREVIOUS_KEYS"):
        raw_ring = os.getenv(env_var) or ""
        for entry in raw_ring.split(","):
            candidate = entry.strip().strip("'\"")
            if not candidate:
                continue
            encoded = candidate.encode("utf-8")
            if encoded not in seen:
                keys.append(encoded)
                seen.add(encoded)

    return keys


def _get_multi_fernet() -> MultiFernet:
    """
    Construct a MultiFernet ring from configured Plaid keys.
    Fails closed if no keys are configured or any key is malformed.
    """
    raw_keys = _parse_plaid_key_ring()
    if not raw_keys:
        raise PlaidKeyConfigurationError(
            "PLAID_ENCRYPTION_KEY (or PLAID_ENCRYPTION_KEYS) is not configured."
        )

    fernets: list[Fernet] = []
    for raw_key in raw_keys:
        try:
            fernets.append(Fernet(raw_key))
        except Exception as exc:
            raise PlaidKeyConfigurationError(
                "Invalid Plaid Fernet key in key ring."
            ) from exc

    return MultiFernet(fernets)


def validate_plaid_keys() -> None:
    """Validate Plaid encryption key ring at application startup."""
    _get_multi_fernet()


def _require_non_empty_str(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlaidCryptoError(f"{label} must be a non-empty string.")
    return value


def encrypt_token(token: str) -> str:
    """
    Encrypt a Plaid access token using the primary key in the MultiFernet ring.
    """
    clean_token = _require_non_empty_str(token, "Plaid access token")
    mf = _get_multi_fernet()
    return mf.encrypt(clean_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a Plaid access token using any active key in the MultiFernet ring.
    """
    clean_ciphertext = _require_non_empty_str(encrypted_token, "Encrypted Plaid token")
    mf = _get_multi_fernet()
    try:
        return mf.decrypt(clean_ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise PlaidTokenDecryptionError(
            "Failed to decrypt Plaid token: invalid ciphertext or key."
        ) from exc


def rotate_token(encrypted_token: str) -> str:
    """
    Re-encrypt an existing Plaid ciphertext token under the current primary key.
    """
    clean_ciphertext = _require_non_empty_str(encrypted_token, "Encrypted Plaid token")
    mf = _get_multi_fernet()
    try:
        return mf.rotate(clean_ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise PlaidTokenDecryptionError(
            "Failed to rotate Plaid token: invalid ciphertext or key."
        ) from exc