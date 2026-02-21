# =============================================================================
# FILE: app/services/sms.py
# DESCRIPTION: SMS sending service. Backwards-compatible wrapper to support
#              callers that pass a User object (send_mfa_code(user)).
#              Low-level phone sender remains a simple stub to replace later.
#              Includes test hooks, structured errors, and provider plugin points.
# =============================================================================

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


# ---- Exceptions ----
class SendMFACodeError(Exception):
    """Base send error."""


class SendMFATransientError(SendMFACodeError):
    """Transient error (retryable)."""


class SendMFAPermanentError(SendMFACodeError):
    """Permanent error (not retryable)."""


# ---- Config / hooks (override in tests or via DI) ----
# Hook for generating codes (test can override)
def _default_generate_code_hook() -> str:
    return f"{secrets.randbelow(10**6):06d}"


_generate_code_hook: Callable[[], str] = _default_generate_code_hook

# Hook for telemetry (operator can swap-in)
_telemetry_hook: Callable[[str, dict], None] | None = None


def register_generate_code_hook(fn: Callable[[], str]) -> None:
    global _generate_code_hook
    _generate_code_hook = fn


def register_telemetry_hook(fn: Callable[[str, dict], None]) -> None:
    global _telemetry_hook
    _telemetry_hook = fn


def _emit_telemetry(evt: str, payload: dict) -> None:
    try:
        if _telemetry_hook:
            _telemetry_hook(evt, payload)
        else:
            logger.debug("telemetry: %s %s", evt, payload)
    except Exception:
        logger.exception("telemetry hook failed for %s", evt)


# ---- Low-level sender (legacy signature) ----
def _send_via_phone(phone_number: str, code: str) -> bool:
    """
    Low-level phone sender (legacy). Keep this trivial for now.
    Replace with a real provider integration that returns True on success.
    """
    try:
        logger.info(
            "[MOCK SMS] Sending MFA code to phone (masked): ****%s",
            phone_number[-4:] if phone_number else "????",
        )
        _emit_telemetry(
            "MFA_SEND_SMS_STUB",
            {"phone_last4": phone_number[-4:] if phone_number else None},
        )
        return True
    except Exception as exc:
        logger.error("Low-level SMS send failed: %s", exc, exc_info=True)
        raise SendMFATransientError("low-level sms send failed") from exc


# ---- Provider gateway (pluggable) ----
def new_send_mfa_code(user: Any, code: str, purpose: str = "setup", persist: bool = True) -> bool:
    """
    Provider entrypoint. Default behaviour:
      - prefer user.primary_phone
      - fallback to user.email (development only)
    Return True on success, False/raise on failure.
    """
    phone = getattr(user, "primary_phone", None)
    email = getattr(user, "email", None)
    user_id = getattr(user, "id", None)

    if phone:
        try:
            ok = _send_via_phone(phone, code)
        except SendMFATransientError:
            _emit_telemetry("MFA_SEND_FAILURE_TRANSIENT", {"user_id": user_id, "mode": "sms"})
            raise
        except Exception as exc:
            _emit_telemetry("MFA_SEND_FAILURE_PERMANENT", {"user_id": user_id, "mode": "sms"})
            raise SendMFAPermanentError("sms provider failure") from exc
        _emit_telemetry("MFA_SEND_SMS_OK", {"user_id": user_id, "mode": "sms"})
        return ok
    elif email:
        # Development fallback: we log and return True.
        logger.info(
            "[MOCK EMAIL] MFA code delivered to email (masked): %s",
            email.split("@")[0] + "@***",
        )
        _emit_telemetry("MFA_SEND_EMAIL_OK", {"user_id": user_id, "mode": "email"})
        return True
    else:
        logger.warning("No delivery address for user id=%s; cannot send MFA code", user_id)
        _emit_telemetry("MFA_SEND_NO_ADDRESS", {"user_id": user_id})
        raise SendMFAPermanentError("no delivery address")


# ---- Wrapper (compat) ----
def send_mfa_code(
    user_or_phone: Any,
    code: str | None = None,
    purpose: str = "setup",
    persist: bool = True,
    retry: int = 0,
    backoff: float = 0.0,
) -> str:
    """
    Backwards-compatible wrapper.

    Supports:
      - send_mfa_code(user_obj) -> returns generated code
      - send_mfa_code(user_obj, code="123456") -> returns the code
      - send_mfa_code(phone_number, code) -> legacy; returns code on success

    Raises SendMFACodeError on failure.
    """
    # legacy phone + code path
    if isinstance(user_or_phone, str):
        phone = user_or_phone
        if not code:
            raise TypeError("Legacy send_mfa_code(phone_number, code) requires a code argument")
        try:
            ok = _send_via_phone(phone, code)
        except SendMFATransientError:
            raise
        except Exception as e:
            raise SendMFAPermanentError(str(e)) from e
        if not ok:
            raise SendMFATransientError("low-level phone send returned False")
        return code

    # user-like object
    user = user_or_phone
    user_id = getattr(user, "id", None)
    if not code:
        code = _generate_code_hook()

    attempt = 0
    while True:
        try:
            ok = new_send_mfa_code(user, code=code, purpose=purpose, persist=persist)
            if not ok:
                raise SendMFATransientError("provider returned False")
            _emit_telemetry("MFA_SEND_OK", {"user_id": user_id, "purpose": purpose})
            return code
        except SendMFAPermanentError as e:
            logger.warning("Permanent send failure for user=%s: %s", user_id, e)
            _emit_telemetry("MFA_SEND_PERMANENT", {"user_id": user_id, "error": str(e)})
            raise
        except SendMFATransientError as e:
            attempt += 1
            _emit_telemetry(
                "MFA_SEND_TRANSIENT",
                {"user_id": user_id, "attempt": attempt, "error": str(e)},
            )
            logger.warning("Transient send failure for user=%s attempt=%s: %s", user_id, attempt, e)
            if attempt > retry:
                raise
            # backoff then retry
            if backoff:
                time.sleep(backoff * attempt)
            continue
        except Exception as e:
            logger.exception("Unexpected exception while sending MFA code for user=%s", user_id)
            _emit_telemetry("MFA_SEND_UNEXPECTED", {"user_id": user_id, "error": str(e)})
            raise SendMFATransientError(str(e)) from e
