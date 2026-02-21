# =============================================================================
# FILE: app/services/pii_manager.py
# DESCRIPTION: PII management service. Provides encryption/decryption for
#              sensitive fields. Uses Fernet symmetric crypto with a key
#              from environment variables. Falls back to stub if misconfigured.
# =============================================================================

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Key Management
# -----------------------------------------------------------------------------
_FERNET: Fernet | None = None


def _init_fernet() -> Fernet | None:
    """
    Initialize a Fernet instance from the PII_ENCRYPTION_KEY environment variable.
    If the key is missing or invalid, return None (stub mode).
    """
    global _FERNET
    if _FERNET is not None:
        return _FERNET

    key = os.getenv("PII_ENCRYPTION_KEY")
    if not key:
        logger.warning("PII_ENCRYPTION_KEY not set. Falling back to stub mode.")
        return None

    try:
        _FERNET = Fernet(key.encode("utf-8"))
        return _FERNET
    except Exception as e:
        logger.error(f"Invalid PII_ENCRYPTION_KEY. Falling back to stub mode: {e}")
        return None


# -----------------------------------------------------------------------------
# Encryption / Decryption
# -----------------------------------------------------------------------------
def encrypt_pii(value: str) -> str:
    """
    Encrypt a PII value using Fernet. If encryption is not configured,
    return a stubbed marker.
    """
    if not value:
        return ""

    f = _init_fernet()
    if not f:
        # Stub fallback
        return f"ENCRYPTED::{value}"

    try:
        token = f.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encrypt PII: {e}", exc_info=True)
        return ""


def decrypt_pii(value: str) -> str:
    """
    Decrypt a PII value using Fernet. If decryption is not configured,
    attempt to strip the stub marker.
    """
    if not value:
        return ""

    f = _init_fernet()
    if not f:
        # Stub fallback
        if value.startswith("ENCRYPTED::"):
            return value.replace("ENCRYPTED::", "", 1)
        return value

    try:
        plain = f.decrypt(value.encode("utf-8"))
        return plain.decode("utf-8")
    except InvalidToken:
        logger.warning("Invalid token provided for PII decryption.")
        return ""
    except Exception as e:
        logger.error(f"Failed to decrypt PII: {e}", exc_info=True)
        return ""
