# =============================================================================
# FILE: app/telemetry/ttl_emit.py
# DESCRIPTION: TTL pulse emitter with lazy Redis client fallback, recursion guard,
#              emit queue, structured trace logging, and safe wrappers.
# =============================================================================

import datetime
import functools
import json
import logging
import threading
from collections.abc import Callable
from time import sleep
from typing import Any

logger = logging.getLogger(__name__)

# --- In-Memory Store & Locks ---
_ttl_data: dict[str, Any] = {}
_data_lock = threading.Lock()

_in_progress = False
_warned_no_redis = False

# Queue entries: (key, timestamp, value, status, ttl_seconds, meta)
_emit_queue: list[tuple[str, str, str | None, str | None, int, dict[str, Any] | None]] = []
_queue_lock = threading.Lock()


def _get_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


def _attempt_flush_queue(client: Any) -> int:
    """
    Atomically flush queued events to Redis via a pipeline-like API (best-effort).

    Returns:
        int: Number of items successfully flushed. Returns 0 on failure or if queue empty.
    """
    with _queue_lock:
        if not _emit_queue:
            return 0

        items = list(_emit_queue)
        count = len(items)

        use_pipeline = hasattr(client, "pipeline") and callable(client.pipeline)
        try:
            if use_pipeline:
                pipe = client.pipeline()
                for key, ts, val, st, ttl_s, meta in items:
                    payload = {
                        "status": st or "N/A",
                        "timestamp": ts,
                        "value": val or "",
                    }
                    if meta:
                        payload.update(meta)
                    if hasattr(pipe, "setex"):
                        pipe.setex(key, ttl_s, json.dumps(payload))
                    else:
                        pipe.set(key, json.dumps(payload), ex=int(ttl_s))

                for attempt in range(1, 3):
                    try:
                        pipe.execute()
                        _emit_queue.clear()
                        logger.info(
                            "🟢 Flushed %d queued TTL emits (attempt %d).",
                            count,
                            attempt,
                        )
                        return count
                    except Exception as e:
                        logger.warning("⚠️ Flush attempt %d failed: %s", attempt, e)
                        if attempt < 2:
                            sleep(0.1)
                        else:
                            logger.error("❌ Final flush failed; queue intact.", exc_info=True)
                            return 0

            else:
                for key, ts, val, st, ttl_s, meta in items:
                    payload = {
                        "status": st or "N/A",
                        "timestamp": ts,
                        "value": val or "",
                    }
                    if meta:
                        payload.update(meta)
                    if hasattr(client, "setex"):
                        client.setex(key, ttl_s, json.dumps(payload))
                    elif hasattr(client, "set"):
                        try:
                            client.set(key, json.dumps(payload), ex=int(ttl_s))
                        except TypeError:
                            client.set(key, json.dumps(payload), int(ttl_s))

                _emit_queue.clear()
                logger.info("🟢 Flushed %d queued TTL emits (serial fallback).", count)
                return count

        except Exception as e:
            logger.exception("Failed flushing emit queue: %s", e)

    # 🔥 REQUIRED FIX: explicit fallback return
    return 0


def flush_emit_queue(client: Any | None) -> int:
    """Public API: drains any emits queued before Redis was ready. Best-effort no-raise."""
    if client:
        try:
            return _attempt_flush_queue(client)
        except Exception as e:
            logger.warning("Failed to flush emit queue: %s", e)
    return 0


def _resolve_client(
    explicit_client: Any | None = None,
    alias_r: Any | None = None,
) -> Any | None:
    """Resolve a Redis-like client in order: explicit, alias, lazy factory."""
    if explicit_client is not None:
        return explicit_client
    if alias_r is not None:
        return alias_r
    try:
        from app.utils.redis_utils import get_redis_client

        return get_redis_client()
    except Exception as e:
        logger.debug("No redis client resolved: %s", e)
        return None


def ttl_emit(
    *,
    key: str,
    value: str | None = None,
    status: str | None = None,
    client: Any | None = None,
    r: Any | None = None,
    ttl: int = 60,
    meta: dict[str, Any] | None = None,
) -> None:
    """Emit a TTL-backed trace to Redis + in-memory store."""
    global _in_progress, _warned_no_redis

    if _in_progress:
        return

    try:
        _in_progress = True
        ts = _get_timestamp()

        with _data_lock:
            _ttl_data[key] = {
                "expires_at": datetime.datetime.now() + datetime.timedelta(seconds=ttl),
                "ttl_seconds": ttl,
                "value": value,
                "status": status,
                "meta": meta,
            }

        resolved = _resolve_client(client, r)
        if resolved is None:
            if not _warned_no_redis:
                logger.warning("TTL emit queued: no Redis available")
                _warned_no_redis = True
            with _queue_lock:
                _emit_queue.append((key, ts, value, status, ttl, meta))
            return

        if _emit_queue:
            flushed = flush_emit_queue(resolved)
            if flushed and _warned_no_redis:
                _warned_no_redis = False

        payload: dict[str, Any] = {
            "status": status or "N/A",
            "timestamp": ts,
            "value": value or "",
        }
        if meta:
            payload.update(meta)

        try:
            if hasattr(resolved, "setex"):
                resolved.setex(key, ttl, json.dumps(payload))
                return

            if hasattr(resolved, "set"):
                try:
                    resolved.set(key, json.dumps(payload), ex=int(ttl))
                    return
                except TypeError:
                    resolved.set(key, json.dumps(payload), int(ttl))
                    return

            if hasattr(resolved, "pipeline") and callable(resolved.pipeline):
                try:
                    pipe = resolved.pipeline()
                    if hasattr(pipe, "setex"):
                        pipe.setex(key, ttl, json.dumps(payload))
                    else:
                        pipe.set(key, json.dumps(payload), ex=int(ttl))
                    pipe.execute()
                    return
                except Exception:
                    logger.debug("Pipeline emit failed; falling through to no-op", exc_info=True)

            logger.debug("Telemetry: resolved client is not Redis-like; treating ttl_emit as no-op")
            return

        except Exception as e:
            logger.warning("Error while writing TTL emit to client: %s", e, exc_info=False)

    finally:
        _in_progress = False


def ttl_summary() -> dict[str, Any]:
    """Return in-memory snapshot of TTL data with remaining TTLs."""
    now = datetime.datetime.now()
    summary: dict[str, Any] = {}
    with _data_lock:
        to_delete: list[str] = []
        for k, d in _ttl_data.items():
            rem = int((d["expires_at"] - now).total_seconds())
            if rem <= -300:
                to_delete.append(k)
                continue
            summary[k] = {
                "expires_at": d["expires_at"],
                "remaining_seconds": max(0, rem),
                "fresh": rem > 0,
                "value": d.get("value"),
                "status": d.get("status"),
                "meta": d.get("meta"),
            }
        for k in to_delete:
            del _ttl_data[k]
    return summary


def emit_boot_trace(
    *,
    domain: str,
    event: str,
    detail: str,
    value: str | None = None,
    status: str = "ok",
    ttl: int = 60,
    client: Any | None = None,
    meta: dict[str, Any] | None = None,
) -> Any:
    """Boot/migration pulse wrapper."""
    key = f"ttl:boot:{domain}:{event}:{detail}"
    return ttl_emit(
        key=key,
        value=value,
        status=status,
        ttl=ttl,
        client=client,
        meta=meta,
    )


def emit_schema_trace(
    domain: str,
    event: str,
    detail: str,
    value: str,
    status: str,
    ttl: int = 60,
    client: Any | None = None,
    meta: dict[str, Any] | None = None,
) -> Any:
    """Schema-enforcing wrapper around ttl_emit."""
    key = f"ttl:{domain}:{event}:{detail}"
    return ttl_emit(
        key=key,
        value=value,
        status=status,
        ttl=ttl,
        client=client,
        meta=meta,
    )


def trace_log(event_type: str, message: str, **meta: Any) -> Any:
    """Structured trace logging backed by ttl_emit."""
    key = f"ttl:trace:{event_type}:{message.replace(' ', '_')}"
    return ttl_emit(
        key=key,
        value=message,
        status="ok",
        ttl=60,
        meta=meta,
    )


def safe_emit(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that swallows any exceptions from telemetry calls."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning("Telemetry failure in %s: %s", fn.__name__, e)

    return wrapper


__all__ = [
    "ttl_emit",
    "ttl_summary",
    "emit_boot_trace",
    "emit_schema_trace",
    "trace_log",
    "safe_emit",
    "flush_emit_queue",
]
