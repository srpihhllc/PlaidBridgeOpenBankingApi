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


class SendMFACodeError(Exception):
    """Base error for MFA code delivery."""


class SendMFATransientError(SendMFACodeError):
    """Retryable MFA delivery error."""


class SendMFAPermanentError(SendMFACodeError):
    """Non-retryable MFA delivery error."""


def _default_generate_code_hook() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


_generate_code_hook: Callable[[], str] = _default_generate_code_hook
_telemetry_hook: Callable[[str, dict], None] | None = None


def register_generate_code_hook(fn: Callable[[], str]) -> None:
    global _generate_code_hook
    _generate_code_hook = fn


def register_telemetry_hook(fn: Callable[[str, dict], None]) -> None:
    global _telemetry_hook
    _telemetry_hook = fn


def _emit_telemetry(evt: str, payload: dict) -> None:
    # Do not put MFA codes or full contact details in telemetry.
    try:
        if _telemetry_hook:
            _telemetry_hook(evt, payload)
        else:
            logger.debug("MFA telemetry: %s %s", evt, payload)
    except Exception:
        logger.exception("Telemetry hook failed for event=%s", evt)


def _send_via_phone(phone_number: str, code: str) -> bool:
    """
    SMS provider integration point.

    Replace this function with your provider's API call. It must return True
    only if the provider accepts the message.
    """
    del phone_number, code
    raise SendMFAPermanentError("SMS provider is not configured; code was not sent.")


def _send_via_email(email: str, code: str) -> bool:
    """
    Email provider integration point.

    Replace this function with your provider's API call. It must return True
    only if the provider accepts the message.
    """
    del email, code
    raise SendMFAPermanentError("Email provider is not configured; code was not sent.")


def new_send_mfa_code(
    user: Any,
    code: str,
    purpose: str = "setup",
    persist: bool = True,
) -> bool:
    """Send a code through a configured provider; never claim a mock send succeeded."""
    del purpose, persist

    phone = (
        getattr(user, "primary_phone", None)
        or getattr(user, "phone_number", None)
        or getattr(user, "phone", None)
        or getattr(user, "business_phone", None)
    )
    email = getattr(user, "email", None)
    user_id = getattr(user, "id", None)

    if phone:
        try:
            sent = _send_via_phone(str(phone), code)
        except SendMFACodeError:
            _emit_telemetry(
                "MFA_SEND_FAILURE",
                {"user_id": user_id, "channel": "sms"},
            )
            raise
        except Exception as exc:
            raise SendMFATransientError("SMS provider failed") from exc

        if not sent:
            raise SendMFATransientError("SMS provider did not accept the message.")

        _emit_telemetry("MFA_SEND_ACCEPTED", {"user_id": user_id, "channel": "sms"})
        return True

    if email:
        try:
            sent = _send_via_email(str(email), code)
        except SendMFACodeError:
            _emit_telemetry(
                "MFA_SEND_FAILURE",
                {"user_id": user_id, "channel": "email"},
            )
            raise
        except Exception as exc:
            raise SendMFATransientError("Email provider failed") from exc

        if not sent:
            raise SendMFATransientError("Email provider did not accept the message.")

        _emit_telemetry("MFA_SEND_ACCEPTED", {"user_id": user_id, "channel": "email"})
        return True

    _emit_telemetry("MFA_SEND_NO_ADDRESS", {"user_id": user_id})
    raise SendMFAPermanentError("User has no configured MFA delivery address.")


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
      send_mfa_code(user_obj)
      send_mfa_code(user_obj, code="123456")
      send_mfa_code(phone_number, code="123456")
    """
    # Legacy phone-number call.
    if isinstance(user_or_phone, str):
        if not code:
            raise TypeError(
                "send_mfa_code(phone_number, code) requires a code argument"
            )

        try:
            sent = _send_via_phone(user_or_phone, code)
        except SendMFACodeError:
            raise
        except Exception as exc:
            raise SendMFATransientError("SMS provider failed") from exc

        if not sent:
            raise SendMFATransientError("SMS provider did not accept the message.")
        return code

    user = user_or_phone
    user_id = getattr(user, "id", None)
    code = code or _generate_code_hook()

    attempt = 0
    while True:
        try:
            sent = new_send_mfa_code(
                user,
                code=code,
                purpose=purpose,
                persist=persist,
            )
            if not sent:
                raise SendMFATransientError("Provider did not accept the message.")

            _emit_telemetry("MFA_SEND_OK", {"user_id": user_id, "purpose": purpose})
            return code

        except SendMFAPermanentError:
            _emit_telemetry(
                "MFA_SEND_PERMANENT",
                {"user_id": user_id, "purpose": purpose},
            )
            raise

        except SendMFATransientError:
            attempt += 1
            _emit_telemetry(
                "MFA_SEND_TRANSIENT",
                {"user_id": user_id, "attempt": attempt},
            )

            if attempt > retry:
                raise

            if backoff > 0:
                time.sleep(backoff * attempt)

        except Exception as exc:
            logger.exception("Unexpected MFA send error for user_id=%s", user_id)
            raise SendMFATransientError("Unexpected MFA delivery failure.") from exc