# =============================================================================
# FILE: app/utils/trace_emitter.py
# DESCRIPTION: Cockpit-grade trace emitter for Redis with TTL and safe fallback.
# =============================================================================

import json
import logging
import time
from typing import Any

from flask import current_app

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

_logger = logging.getLogger(__name__)


def emit_trace(event_type: str, detail: Any, ttl: int = 60) -> None:
    """
    Emit a trace event to Redis with a TTL.
    - Namespaced by event_type and timestamp for uniqueness.
    - Falls back gracefully if Redis is unavailable.
    - Logs success/failure for cockpit-grade operator visibility.
    """
    r = get_redis_client()
    if not r:
        _logger.error(
            "[emit_trace] Redis unavailable — cannot emit trace",
            extra={"event_type": event_type, "detail": detail},
        )
        return

    key = f"trace:{event_type}:{int(time.time())}"
    payload: dict[str, Any] = {
        "event_type": event_type,
        "detail": detail,
        "timestamp": time.time(),
    }

    try:
        r.setex(key, ttl, json.dumps(payload))
        _logger.debug(
            "[emit_trace] Trace emitted successfully",
            extra={"key": key, "event_type": event_type},
        )
    except Exception as exc:
        _logger.exception(
            "[emit_trace] Failed to emit trace",
            extra={"key": key, "event_type": event_type, "error": str(exc)},
        )
        try:
            current_app.logger.error(f"[emit_trace] Failed to emit trace {key}: {exc}")
        except Exception:
            # Fallback if current_app is not available
            pass
