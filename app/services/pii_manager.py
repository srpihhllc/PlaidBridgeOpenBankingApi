# =============================================================================
# FILE: app/services/pii_manager.py
# DESCRIPTION: Fail-closed PII management service with MultiFernet key rotation.
#              Never falls back to plaintext or stub markers in any environment.
# =============================================================================

from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

logger = logging.getLogger(__name__)


class PIICryptoError(Exception):
    """Base exception for PII cryptographic failures."""


class PIIKeyConfigurationError(PIICryptoError):
    """Raised when PII encryption key configuration is missing or invalid."""


class PIIDecryptionError(PIICryptoError):
    """Raised when PII ciphertext cannot be decrypted or rotated."""


def _parse_pii_key_ring() -> list[bytes]:
    """
    Build an ordered list of Fernet keys (primary key first for encryption,
    followed by fallback/previous keys for decryption and rotation).
    """
    keys: list[bytes] = []
    seen: set[bytes] = set()

    primary = (os.getenv("PII_ENCRYPTION_KEY") or "").strip().strip("'\"")
    if primary:
        encoded = primary.encode("utf-8")
        keys.append(encoded)
        seen.add(encoded)

    for env_var in ("PII_ENCRYPTION_KEYS", "PII_PREVIOUS_KEYS"):
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
    Construct a MultiFernet ring from configured PII keys.
    Fails closed if keys are missing or invalid in any environment.
    """
    raw_keys = _parse_pii_key_ring()
    if not raw_keys:
        raise PIIKeyConfigurationError(
            "PII_ENCRYPTION_KEY (or PII_ENCRYPTION_KEYS) is not configured."
        )

    fernets: list[Fernet] = []
    for raw_key in raw_keys:
        try:
            fernets.append(Fernet(raw_key))
        except Exception as exc:
            raise PIIKeyConfigurationError(
                "Invalid PII Fernet key in key ring."
            ) from exc

    return MultiFernet(fernets)


def validate_pii_keys() -> None:
    """Validate PII encryption key ring at application startup."""
    _get_multi_fernet()


def _validate_pii_input(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise PIICryptoError(f"{label} must be a string.")
    return value


def encrypt_pii(value: str) -> str:
    """
    Encrypt a PII value using the primary key in the MultiFernet ring.
    Returns '' for empty string input; fails closed on invalid types or keys.
    """
    clean_value = _validate_pii_input(value, "PII plaintext")
    if clean_value == "":
        return ""

    mf = _get_multi_fernet()
    try:
        return mf.encrypt(clean_value.encode("utf-8")).decode("utf-8")
    except PIICryptoError:
        raise
    except Exception as exc:
        logger.error("Failed to encrypt PII value.", exc_info=True)
        raise PIICryptoError("Failed to encrypt PII value.") from exc


def decrypt_pii(value: str) -> str:
    """
    Decrypt a PII ciphertext value using any active key in the MultiFernet ring.
    Returns '' for empty string input; fails closed on invalid tokens or keys.
    """
    clean_ciphertext = _validate_pii_input(value, "PII ciphertext")
    if clean_ciphertext == "":
        return ""

    mf = _get_multi_fernet()
    try:
        return mf.decrypt(clean_ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.warning("Invalid or undecryptable PII ciphertext token.")
        raise PIIDecryptionError(
            "Failed to decrypt PII value: invalid ciphertext or key."
        ) from exc
    except PIICryptoError:
        raise
    except Exception as exc:
        logger.error("Failed to decrypt PII value.", exc_info=True)
        raise PIIDecryptionError("Failed to decrypt PII value.") from exc


def rotate_pii(value: str) -> str:
    """
    Re-encrypt an existing PII ciphertext token under the current primary key.
    """
    clean_ciphertext = _validate_pii_input(value, "PII ciphertext")
    if clean_ciphertext == "":
        return ""

    mf = _get_multi_fernet()
    try:
        return mf.rotate(clean_ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise PIIDecryptionError(
            "Failed to rotate PII value: invalid ciphertext or key."
        ) from exc