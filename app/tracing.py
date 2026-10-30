# =============================================================================
# FILE: app/tracing.py
# DESCRIPTION: Cockpit-grade request and error tracing with rich stack frame
#              extraction, line code snippets, and Redis persistence.
# =============================================================================

from __future__ import annotations

import json
import linecache
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import current_app

from app.utils.redis_utils import get_redis_client


def _client() -> Any:
    """Fetch the Redis client lazily so tests can stub it before use."""
    return get_redis_client()


def _extract_rich_stack_frames(tb: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Extract stack frames with line numbers, code snippets, and call details."""
    if tb is None:
        _, _, tb = sys.exc_info()

    frames: List[Dict[str, Any]] = []
    if not tb:
        return frames

    try:
        for frame in traceback.extract_tb(tb):
            filename = frame.filename
            lineno = frame.lineno
            snippet: List[Dict[str, Any]] = []

            try:
                if lineno is not None:
                    for line_number in range(max(1, lineno - 2), lineno + 3):
                        code_line = linecache.getline(filename, line_number)
                        if code_line:
                            snippet.append(
                                {
                                    "line_number": line_number,
                                    "code": code_line.rstrip(),
                                    "is_error_line": line_number == lineno,
                                }
                            )
            except Exception:
                pass

            frames.append(
                {
                    "file": filename,
                    "line": lineno,
                    "function": frame.name,
                    "code_line": frame.line or "",
                    "snippet": snippet,
                }
            )
    except Exception:
        pass

    return frames


def handle_traced_error(error: Exception) -> Dict[str, Any]:
    """Build an enriched error payload and emit it to Redis."""
    _, _, exc_tb = sys.exc_info()
    frames = _extract_rich_stack_frames(exc_tb)
    faulty_frame = frames[-1] if frames else {}

    payload: Dict[str, Any] = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "faulty_file": faulty_frame.get("file"),
        "faulty_line": faulty_frame.get("line"),
        "faulty_function": faulty_frame.get("function"),
        "faulty_code": faulty_frame.get("code_line"),
        "stack_frames": frames,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    trace_log(f"errors/traced/{type(error).__name__}", payload, ttl=1800)
    return payload


def trace_log(event_type: str, payload: Any, ttl: int = 3600) -> None:
    """Emit a trace with a TTL and timestamp."""
    client = _client()
    if not client:
        _log_unavailable(f"trace_log({event_type})")
        return

    key = f"trace:{event_type}:{datetime.now(timezone.utc).isoformat()}"
    value = json.dumps(
        {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        client.setex(key, ttl, value)
        print(f"📝 Emitted trace: {key}")
    except Exception as exc:
        _log_failure(f"trace_log({event_type})", exc)


def trace_boot(event_type: str, detail: Any) -> None:
    """Emit a boot-time trace."""
    trace_log(f"boot/{event_type}", detail)


def trace_error(context: str, error: Exception | str) -> None:
    """Emit an error trace, including stack context when available."""
    _, _, exc_tb = sys.exc_info()
    frames = _extract_rich_stack_frames(exc_tb) if exc_tb else []
    faulty_frame = frames[-1] if frames else {}

    payload: Any
    if frames:
        payload = {
            "error": str(error),
            "error_type": type(error).__name__ if isinstance(error, Exception) else "Error",
            "faulty_file": faulty_frame.get("file"),
            "faulty_line": faulty_frame.get("line"),
            "faulty_function": faulty_frame.get("function"),
            "faulty_code": faulty_frame.get("code_line"),
            "stack_frames": frames,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        payload = str(error)

    trace_log(f"errors/{context}", payload, ttl=1800)


def trace_heartbeat(tile: str, status: str = "ok") -> None:
    """Emit a short-lived heartbeat for cockpit tiles."""
    trace_log(f"heartbeat/{tile}", {"status": status}, ttl=300)


def check_redis_health() -> None:
    """Emit a trace confirming Redis connectivity."""
    client = _client()
    if not client:
        _log_unavailable("check_redis_health")
        return

    try:
        pong = client.ping()
        trace_log("boot/redis_health", f"Redis ping: {pong}")
    except Exception as exc:
        trace_error("redis_ping", exc)


def emit_context_entry(name: str) -> None:
    """Emit a trace when entering an application context."""
    trace_log(f"context/{name}/entered", "App context entered")


def emit_context_exit(name: str) -> None:
    """Emit a trace when exiting an application context."""
    trace_log(f"context/{name}/exited", "App context exited")


def _log_unavailable(context: str) -> None:
    message = f"[{context}] Redis unavailable — trace not recorded"
    try:
        current_app.logger.error(message)
    except RuntimeError:
        print(f"❌ {message}")


def _log_failure(context: str, error: Exception) -> None:
    message = f"[{context}] Failed to write trace to Redis: {error}"
    try:
        current_app.logger.error(message)
    except RuntimeError:
        print(f"❌ {message}")


def trace_session_warning(model_name: str, context: str = "") -> None:
    """Emit a trace when unsafe `.query` access is detected."""
    payload = {
        "model": model_name,
        "context": context or "unknown",
        "warning": "Unsafe .query access detected; use db.session.query() instead",
    }
    trace_log("session/warning", payload, ttl=900)