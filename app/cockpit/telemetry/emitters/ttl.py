"""
Compatibility wrapper for cockpit telemetry TTL emits.

Provides:
- emit_ttl_pulse(key, ttl_seconds, *, status="ok", value=None)
- ttl_summary() -> dict[str, Any]

Delegates to app.telemetry.ttl_emit when available and falls back to an
in-memory store otherwise.
"""

from __future__ import annotations

import datetime
import importlib
import logging
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)


class _CoreTTLEmitter(Protocol):
    def ttl_emit(
        self,
        *,
        key: str,
        ttl: int,
        status: str,
        value: str | None,
    ) -> None: ...

    def ttl_summary(self) -> dict[str, Any]: ...


def _load_core_ttl() -> _CoreTTLEmitter | None:
    """Load the core emitter dynamically, without a duplicate import binding."""
    try:
        module = importlib.import_module("app.telemetry.ttl_emit")
        emitter = cast(_CoreTTLEmitter, module)

        if not callable(getattr(emitter, "ttl_emit", None)):
            raise AttributeError("Core TTL module has no callable ttl_emit")
        if not callable(getattr(emitter, "ttl_summary", None)):
            raise AttributeError("Core TTL module has no callable ttl_summary")

        return emitter
    except Exception as exc:  # pragma: no cover - depends on runtime environment
        logger.debug("Core TTL emitter not available: %s", exc)
        return None


_core_ttl = _load_core_ttl()
_fallback_store: dict[str, dict[str, Any]] = {}


def emit_ttl_pulse(
    key: str,
    ttl_seconds: int,
    *,
    status: str = "ok",
    value: str | None = None,
) -> None:
    """Emit a TTL pulse through the core emitter or the in-memory fallback."""
    if _core_ttl is not None:
        try:
            _core_ttl.ttl_emit(
                key=key,
                ttl=ttl_seconds,
                status=status,
                value=value,
            )
            return
        except Exception as exc:
            logger.warning(
                "emit_ttl_pulse: core ttl_emit failed: %s",
                exc,
                exc_info=False,
            )

    try:
        _fallback_store[key] = {
            "expires_at": datetime.datetime.now()
            + datetime.timedelta(seconds=ttl_seconds),
            "remaining_seconds": ttl_seconds,
            "fresh": True,
            "value": value,
            "status": status,
        }
    except Exception as exc:
        logger.debug("emit_ttl_pulse fallback failed: %s", exc)


def ttl_summary() -> dict[str, Any]:
    """Return a summary from the core emitter or the in-memory fallback."""
    if _core_ttl is not None:
        try:
            core_summary = _core_ttl.ttl_summary()
            if isinstance(core_summary, dict):
                return core_summary
            logger.warning(
                "ttl_summary: core ttl_summary returned a non-dict value"
            )
        except Exception as exc:
            logger.warning(
                "ttl_summary: core ttl_summary failed: %s",
                exc,
                exc_info=False,
            )

    now = datetime.datetime.now()
    fallback_summary: dict[str, Any] = {}

    for key, entry in list(_fallback_store.items()):
        expires_at = entry["expires_at"]
        remaining = int((expires_at - now).total_seconds())

        fallback_summary[key] = {
            "expires_at": expires_at,
            "remaining_seconds": max(0, remaining),
            "fresh": remaining > 0,
            "value": entry.get("value"),
            "status": entry.get("status"),
            "meta": None,
        }

        if remaining <= -300:
            del _fallback_store[key]

    return fallback_summary


__all__ = ["emit_ttl_pulse", "ttl_summary"]