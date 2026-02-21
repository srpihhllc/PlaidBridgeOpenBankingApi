# =============================================================================
# FILE: app/utils/latency.py
# DESCRIPTION: Helper to measure stage latency and emit TTL traces.
#              Supports both new and legacy call signatures.
# =============================================================================

import logging
import time
from typing import Any

from app.utils.ttl_emit import ttl_emit

logger = logging.getLogger(__name__)


def _call_ttl_emit(r: Any, key: str, value: str, ttl_seconds: int) -> None:
    """
    Invoke ttl_emit robustly, tolerating different signatures across
    environments and test doubles.

    Attempts multiple call styles in order:
      1. Positional: ttl_emit(r, key, value, ttl)
      2. Keyword:    ttl_emit(key=..., value=..., r=..., ttl=...)
      3. Keyword alt:ttl_emit(key=..., r=..., value=..., ttl=...)
      4. Minimal:    ttl_emit(r, key, value)

    Raises:
        TypeError: if no supported signature works.
    """
    try:
        ttl_emit(r, key, value, ttl_seconds)
        return
    except TypeError:
        pass
    try:
        ttl_emit(key=key, value=value, r=r, ttl=ttl_seconds)
        return
    except TypeError:
        pass
    except Exception as e:
        # Catch all non-TypeError exceptions (useful for test doubles)
        logger.debug("ttl_emit call style failed (keyword attempt 2): %s", e)
        pass
    try:
        ttl_emit(key=key, r=r, value=value, ttl=ttl_seconds)
        return
    except Exception as e:
        logger.debug("ttl_emit call style failed (keyword alt): %s", e)
        pass
    try:
        ttl_emit(r, key, value)
        return
    except Exception as e:
        logger.debug("ttl_emit call style failed (minimal): %s", e)
        pass

    logger.warning("ttl_emit signature mismatch for key=%s; no call succeeded", key)
    raise TypeError("ttl_emit has an unexpected signature; cannot call it reliably.")


def emit_latency_trace(*args: Any, **kwargs: Any) -> None:
    """
    Emit a latency trace with TTL.

    Supports both new and legacy call signatures:

    New form:
        emit_latency_trace(stage, request_uuid, start_ts, r[, ttl_seconds])
        Example:
            emit_latency_trace("auth", "req-123", time.time(), redis_client)

    Legacy form:
        emit_latency_trace(endpoint, latency_ms, r[, ttl_seconds])
        Example:
            emit_latency_trace("user_login", 123.45, redis_client)

    Keyword-only equivalents are also supported.

    The payload (value) emitted is always a string:
    - New form: "latency_ms:{duration_in_ms}"
    - Legacy form: "{latency_in_seconds_as_float_string}"
    """
    # --- New signature (positional) ---
    if len(args) >= 4:
        stage, request_uuid, start_ts, r = args[:4]
        ttl_seconds = args[4] if len(args) >= 5 else kwargs.get("ttl_seconds", 300)
        try:
            duration_ms = int((time.time() - float(start_ts)) * 1000)
        except Exception:
            duration_ms = 0
        key = f"ttl:flow:oauth:google:{stage}:latency:{request_uuid}"
        value = f"latency_ms:{duration_ms}"
        _call_ttl_emit(r, key, value, int(ttl_seconds))
        return

    # --- Legacy signature (positional) ---
    if len(args) == 3:
        endpoint, latency_ms, r = args
        # NOTE: Unifying TTL to 300s for consistency across new and legacy traces.
        ttl_seconds = kwargs.get("ttl_seconds", 300)
        try:
            latency_val = float(latency_ms)
        except Exception:
            try:
                latency_val = float(str(latency_ms))
            except Exception:
                latency_val = 0.0
        key = f"latency:{endpoint}"
        value = str(latency_val)
        _call_ttl_emit(r, key, value, int(ttl_seconds))
        return

    # --- New signature (keyword-only) ---
    if {"stage", "request_uuid", "start_ts", "r"}.issubset(kwargs):
        stage = kwargs["stage"]
        request_uuid = kwargs["request_uuid"]
        start_ts = kwargs["start_ts"]
        r = kwargs["r"]
        ttl_seconds = kwargs.get("ttl_seconds", 300)
        try:
            duration_ms = int((time.time() - float(start_ts)) * 1000)
        except Exception:
            duration_ms = 0
        key = f"ttl:flow:oauth:google:{stage}:latency:{request_uuid}"
        value = f"latency_ms:{duration_ms}"
        _call_ttl_emit(r, key, value, int(ttl_seconds))
        return

    # --- Legacy signature (keyword-only) ---
    if {"endpoint", "latency_ms", "r"}.issubset(kwargs):
        endpoint = kwargs["endpoint"]
        latency_ms = kwargs["latency_ms"]
        r = kwargs["r"]
        # NOTE: Unifying TTL to 300s for consistency across new and legacy traces.
        ttl_seconds = kwargs.get("ttl_seconds", 300)
        try:
            latency_val = float(latency_ms)
        except Exception:
            try:
                latency_val = float(str(latency_ms))
            except Exception:
                latency_val = 0.0
        key = f"latency:{endpoint}"
        value = str(latency_val)
        _call_ttl_emit(r, key, value, int(ttl_seconds))
        return

    logger.error("emit_latency_trace called with unsupported args=%s kwargs=%s", args, kwargs)
    raise TypeError(
        "emit_latency_trace expects either "
        "(stage, request_uuid, start_ts, r[, ttl_seconds]) "
        "or (endpoint, latency_ms, r[, ttl_seconds])"
    )
