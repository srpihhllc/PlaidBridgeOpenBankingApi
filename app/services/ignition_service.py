#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/ignition_service.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from flask import session

from app.constants import OPERATOR_MODE_KEY


DEFAULT_OPERATOR_TTL_SECONDS = 900


class IgnitionError(Exception):
    """Raised when operator mode cannot be enabled."""


def enable_operator_mode(
    *,
    actor: Any,
    ttl_seconds: int = DEFAULT_OPERATOR_TTL_SECONDS,
) -> datetime:
    """
    Enable operator mode for an already-verified actor.

    The caller must perform authentication and authorization checks before
    invoking this service.
    """
    if actor is None:
        raise IgnitionError("An authenticated actor is required.")

    if ttl_seconds <= 0:
        raise IgnitionError("Operator mode TTL must be positive.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)

    # Store a self-contained, explicitly expiring value. Do not write
    # unrelated identity or role fields into the session.
    session[OPERATOR_MODE_KEY] = {
        "enabled": True,
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "actor_id": str(getattr(actor, "id", "")),
    }

    session.modified = True
    return expires_at


def disable_operator_mode() -> None:
    """Remove operator mode from the current session."""
    session.pop(OPERATOR_MODE_KEY, None)
    session.modified = True


def operator_mode_is_active() -> bool:
    """Return whether the current session contains an unexpired mode."""
    value = session.get(OPERATOR_MODE_KEY)

    if not isinstance(value, dict) or value.get("enabled") is not True:
        return False

    expires_at_raw = value.get("expires_at")
    if not expires_at_raw:
        disable_operator_mode()
        return False

    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
    except (TypeError, ValueError):
        disable_operator_mode()
        return False

    if expires_at <= datetime.now(timezone.utc):
        disable_operator_mode()
        return False

    return True


def operator_mode_expires_at() -> datetime | None:
    """Return the expiry time if operator mode is currently active."""
    if not operator_mode_is_active():
        return None

    value = session.get(OPERATOR_MODE_KEY)
    return datetime.fromisoformat(value["expires_at"])