# app/cockpit/telemetry/emitters/ttl.py

"""
Compatibility wrapper for cockpit telemetry TTL emits.

Provides:
- emit_ttl_pulse(key, ttl_seconds, *, status="ok", value=None)
- ttl_summary() -> dict

Delegates to app.telemetry.ttl_emit when available and falls back to an
in-memory store otherwise.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Try to import the real TTL emitter; if unavailable, provide a safe stub.
try:
    from app.telemetry import ttl_emit as core_ttl  # module

    _HAS_CORE = True
except Exception as e:  # pragma: no cover - fallback in local/test environments
    logger.debug("Core TTL emitter not available: %s", e)
    _HAS_CORE = False
    core_ttl = None


def emit_ttl_pulse(
    key: str,
    ttl_seconds: int,
    *,
    status: str = "ok",
    value: str | None = None,
) -> None:
    """
    Emit a TTL pulse for the given key with ttl_seconds.
    Delegates to app.telemetry.ttl_emit.ttl_emit when available.
    """
    if _HAS_CORE and core_ttl is not None:
        try:
            core_ttl.ttl_emit(key=key, ttl=ttl_seconds, status=status, value=value)
            return
        except Exception as e:
            logger.warning("emit_ttl_pulse: core ttl_emit failed: %s", e, exc_info=False)

    # Fallback: maintain an in-memory timestamp to keep UI happy
    try:
        _fallback_store[key] = {
            "expires_at": datetime.datetime.now() + datetime.timedelta(seconds=ttl_seconds),
            "remaining_seconds": ttl_seconds,
            "fresh": True,
            "value": value,
            "status": status,
        }
    except Exception as e:
        logger.debug("emit_ttl_pulse fallback failed: %s", e)


def ttl_summary() -> dict[str, Any]:
    """
    Return TTL summary.
    If the core emitter is available, delegate; otherwise return the fallback store snapshot.
    """
    if _HAS_CORE and core_ttl is not None:
        try:
            return core_ttl.ttl_summary()
        except Exception as e:
            logger.warning("ttl_summary: core ttl_summary failed: %s", e, exc_info=False)

    # Fallback snapshot
    now = datetime.datetime.now()
    out: dict[str, Any] = {}
    for k, v in list(_fallback_store.items()):
        rem = int((v["expires_at"] - now).total_seconds())
        out[k] = {
            "expires_at": v["expires_at"],
            "remaining_seconds": max(0, rem),
            "fresh": rem > 0,
            "value": v.get("value"),
            "status": v.get("status"),
            "meta": None,
        }
        if rem <= -300:
            del _fallback_store[k]
    return out


# Minimal in-module fallback store used only when core emitter isn't available.
_fallback_store: dict[str, dict] = {}

__all__ = ["emit_ttl_pulse", "ttl_summary"]
