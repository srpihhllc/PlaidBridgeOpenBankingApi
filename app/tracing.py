# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tracing.py

import json
import linecache
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import current_app

from app.utils.redis_utils import (
    get_redis_client,
)  # ✅ centralised, SSL‑safe client


# -------------------------------------------------------------------------
# LAZY REDIS CLIENT — never call Redis at import time
# -------------------------------------------------------------------------
def _client():
    """
    Always fetch the Redis client lazily so tests can stub it
    before any Redis calls occur.
    """
    return get_redis_client()


# -------------------------------------------------------------------------
# STACK FRAME EXTRACTION HELPERS
# -------------------------------------------------------------------------
def _extract_rich_stack_frames(tb: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Extract enriched stack frames with line numbers, code snippets, and call site details.
    """
    if tb is None:
        _, _, tb = sys.exc_info()
    frames: List[Dict[str, Any]] = []
    if not tb:
        return frames

    try:
        extracted = traceback.extract_tb(tb)
        for frame in extracted:
            filename, lineno, funcname, line_text = (
                frame.filename,
                frame.lineno,
                frame.name,
                frame.line,
            )
            snippet = []
            try:
                start_line = max(1, lineno - 2)
                end_line = lineno + 2
                for l_num in range(start_line, end_line + 1):
                    code_l = linecache.getline(filename, l_num)
                    if code_l:
                        snippet.append(
                            {
                                "line_number": l_num,
                                "code": code_l.rstrip(),
                                "is_error_line": (l_num == lineno),
                            }
                        )
            except Exception:
                pass

            frames.append(
                {
                    "file": filename,
                    "line": lineno,
                    "function": funcname,
                    "code_line": line_text or "",
                    "snippet": snippet,
                }
            )
    except Exception:
        pass

    return frames


def handle_traced_error(error: Exception) -> Dict[str, Any]:
    """
    Custom exception handler to enrich error trace payloads with line numbers,
    code snippets, and stack frames, then emit to Redis.
    """
    _, _, exc_tb = sys.exc_info()
    frames = _extract_rich_stack_frames(exc_tb)
    faulty_frame = frames[-1] if frames else {}

    payload = {
        "error_type": type(error).__name__ if error else "Exception",
        "error_message": str(error),
        "faulty_file": faulty_frame.get("file"),
        "faulty_line": faulty_frame.get("line"),
        "faulty_function": faulty_frame.get("function"),
        "faulty_code": faulty_frame.get("code_line"),
        "stack_frames": frames,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    context = type(error).__name__ if error else "general"
    trace_log(f"errors/traced/{context}", payload, ttl=1800)
    return payload


# -------------------------------------------------------------------------
# TRACE EMITTERS
# -------------------------------------------------------------------------
def trace_log(event_type, payload, ttl=3600):
    """
    Emit a trace with TTL and timestamp.
    """
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
    except Exception as e:
        _log_failure(f"trace_log({event_type})", e)


def trace_boot(event_type, detail):
    """Shortcut for boot-time traces."""
    trace_log(f"boot/{event_type}", detail)


def trace_error(context, error):
    """Emit error trace with enriched stack trace context if available."""
    _, _, exc_tb = sys.exc_info()
    frames = _extract_rich_stack_frames(exc_tb) if exc_tb else []
    faulty_frame = frames[-1] if frames else {}

    if frames:
        payload = {
            "error": str(error),
            "error_type": (
                type(error).__name__
                if isinstance(error, Exception)
                else "Error"
            ),
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


def trace_heartbeat(tile, status="ok"):
    """Emit a short-lived heartbeat for cockpit tiles."""
    trace_log(f"heartbeat/{tile}", {"status": status}, ttl=300)


def check_redis_health():
    """Emit a trace confirming Redis connectivity."""
    client = _client()
    if not client:
        _log_unavailable("check_redis_health")
        return

    try:
        pong = client.ping()
        trace_log("boot/redis_health", f"Redis ping: {pong}")
    except Exception as e:
        trace_error("redis_ping", e)


def emit_context_entry(name):
    """Emit trace when entering app context."""
    trace_log(f"context/{name}/entered", "App context entered")


def emit_context_exit(name):
    """Emit trace when exiting app context."""
    trace_log(f"context/{name}/exited", "App context exited")


# -------------------------------------------------------------------------
# INTERNAL HELPERS
# -------------------------------------------------------------------------
def _log_unavailable(context):
    msg = f"[{context}] Redis unavailable — trace not recorded"
    try:
        current_app.logger.error(msg)
    except RuntimeError:
        # current_app may not be active
        print(f"❌ {msg}")


def _log_failure(context, error):
    msg = f"[{context}] Failed to write trace to Redis: {error}"
    try:
        current_app.logger.error(msg)
    except RuntimeError:
        print(f"❌ {msg}")


def trace_session_warning(model_name: str, context: str = ""):
    """
    Emit a trace when unsafe .query access is detected.
    Helps operators spot session drift between test and prod.
    """
    payload = {
        "model": model_name,
        "context": context or "unknown",
        "warning": "Unsafe .query access detected; use db.session.query() instead",
    }
    trace_log("session/warning", payload, ttl=900)