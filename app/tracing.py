# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tracing.py

import json
from datetime import datetime

from flask import current_app

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client


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

    key = f"trace:{event_type}:{datetime.utcnow().isoformat()}"
    value = json.dumps(
        {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
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
    """Emit error trace with context."""
    trace_log(f"errors/{context}", str(error), ttl=1800)


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
