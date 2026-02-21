# =============================================================================
# FILE: app/utils/ttl_emit.py
# DESCRIPTION: Compatibility shim that forwards to the canonical implementation
#              under app.telemetry.ttl_emit when available. Avoids direct
#              circular imports and provides safe no-op fallbacks for tests.
# =============================================================================

import importlib
from collections.abc import Callable
from typing import Any

_ttl_emit_impl: Callable[..., Any] | None = None


def _default_ttl_summary() -> dict:
    return {}


def _default_emit_boot_trace(*_args: Any, **_kwargs: Any) -> None:
    return None


def _default_safe_emit(fn: Callable[..., Any]) -> Callable[..., Any]:
    return fn


def _default_flush_emit_queue(client: Any = None) -> int:
    return 0


# public fallbacks (may be replaced by the real telemetry implementation)
ttl_summary: Callable[[], dict] = _default_ttl_summary
emit_boot_trace: Callable[..., None] = _default_emit_boot_trace
safe_emit: Callable[[Callable[..., Any]], Callable[..., Any]] = _default_safe_emit
flush_emit_queue: Callable[..., int] = _default_flush_emit_queue

# Try to import the full implementation lazily by module name to avoid import cycles.
try:
    telemetry_mod = importlib.import_module("app.telemetry.ttl_emit")
    # Only use the telemetry implementation if it's actually a different module
    if telemetry_mod is not None and getattr(telemetry_mod, "__name__", "") != __name__:
        _ttl_emit_impl = getattr(telemetry_mod, "ttl_emit", None)
        ttl_summary = getattr(telemetry_mod, "ttl_summary", ttl_summary)
        emit_boot_trace = getattr(telemetry_mod, "emit_boot_trace", emit_boot_trace)
        safe_emit = getattr(telemetry_mod, "safe_emit", safe_emit)
        flush_emit_queue = getattr(telemetry_mod, "flush_emit_queue", flush_emit_queue)
except Exception:
    # Leave safe no-op fallbacks in place if the telemetry implementation cannot be imported.
    _ttl_emit_impl = None


def ttl_emit(*args: Any, **kwargs: Any) -> Any:
    """
    Forward to the real implementation when available, otherwise act as a safe no-op.
    Accepts both positional and keyword styles and returns whatever the implementation returns
    or None when no implementation is available.
    """
    if _ttl_emit_impl is None:
        return None
    return _ttl_emit_impl(*args, **kwargs)


__all__ = [
    "ttl_emit",
    "ttl_summary",
    "emit_boot_trace",
    "safe_emit",
    "flush_emit_queue",
]
