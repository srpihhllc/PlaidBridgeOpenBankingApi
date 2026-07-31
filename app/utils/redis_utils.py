# =============================================================================
# FILE: app/utils/redis_utils.py
# DESCRIPTION: Cockpit‑grade Redis client with health pulses, startup‑emit
#              buffering, cluster debug flag store, and connection‑failure
#              metrics. Defensive about SSL kwargs and provides DISABLE_REDIS
#              guard for migrations/CLI. Normalizes URIs to avoid passing
#              unsupported 'ssl' kwargs and guarantees a clean Redis PING on
#              init when available.
# =============================================================================

from __future__ import annotations

import json
import logging
import os
from datetime import UTC
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from flask import current_app, has_app_context
from redis import Redis

from app.constants.telemetry_keys import (
    REDIS_FAIL_TTL,
    REDIS_PING_KEY,
    REDIS_PING_SUCCESS_KEY,
    REDIS_PING_SUCCESS_TS_KEY,
    REDIS_PING_TTL,
    REDIS_QUEUE_FLUSH_KEY,
    REDIS_QUEUE_FLUSH_TTL,
)
from app.telemetry.ttl_emit import flush_emit_queue, ttl_emit

logger = logging.getLogger(__name__)

REDIS_DEBUG_FLAGS_HASH: str = "app:config:debug_flags"

# -------------------------------------------------------------------------
# Metrics Counter (mocked if missing)
# -------------------------------------------------------------------------
try:
    # app.metrics may be untyped; if absent, provide a noop counter to keep runtime behavior
    from app.metrics import REDIS_CONNECT_FAILURES_COUNTER  # type: ignore
except Exception:

    class _MockCounter:
        def inc(self, *args: Any, **kwargs: Any) -> None:
            return None

    REDIS_CONNECT_FAILURES_COUNTER = _MockCounter()
    logger.warning("Redis connection-failures counter is mocked.")


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _get_utc_timestamp() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_redis_uri(uri: str) -> tuple[str, bool]:
    """
    Normalize Redis URI to avoid passing unsupported kwargs to redis-py:
    - If scheme is 'redis+ssl' -> 'rediss'
    - If scheme is 'redis' and query contains ssl=true, promote to 'rediss'
    - If credentials are provided but username is missing (e.g. redis://:pass@host:port),
      insert a safe default username ("default") so redis-py and some hosted providers
      that require a username/password form work correctly.
    - Remove 'ssl' from the query string so TLS is inferred from the scheme only.

    Returns:
      (normalized_uri, tls_enabled)
    """
    if not uri:
        return uri, False

    parsed = urlparse(uri)

    # Normalize 'redis+ssl' -> 'rediss'
    scheme = parsed.scheme
    if scheme.lower() == "redis+ssl":
        scheme = "rediss"

    # Parse and sanitize query params, possibly promoting tls
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ssl_q = q.pop("ssl", "").strip().lower()  # remove ssl from query if present

    promote_tls = False
    if ssl_q in {"1", "true", "yes"} and scheme == "redis":
        scheme = "rediss"
        promote_tls = True

    # If credentials exist but username is empty (e.g. ":password@host"),
    # insert a default username ("default") for compatibility with ACL-enabled Redis.
    username = parsed.username
    password = parsed.password
    hostname = parsed.hostname or ""
    port = parsed.port

    netloc = parsed.netloc
    if username is None and password:
        if port:
            netloc = f"default:{password}@{hostname}:{port}"
        else:
            netloc = f"default:{password}@{hostname}"
    else:
        netloc = parsed.netloc

    new_query = urlencode(q, doseq=True)
    normalized = urlunparse(
        (
            scheme,
            netloc,
            parsed.path or "",
            parsed.params or "",
            new_query,
            parsed.fragment or "",
        )
    )

    tls_enabled = scheme == "rediss" or promote_tls
    return normalized, tls_enabled


def _masked_endpoint(uri: str) -> str:
    """
    Mask credentials in a URI for safe logging:
    Examples:
      - rediss://user:****@host:port/db
      - redis://default:****@host/db
    """
    try:
        p = urlparse(uri)
        username = p.username
        password = p.password
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        path = p.path or ""

        if username or password:
            display_user = username if username else "default"
            return f"{p.scheme}://{display_user}:****@{host}{port}{path}"
        else:
            netloc = p.netloc or ""
            return f"{p.scheme}://{netloc}{path}"
    except Exception:
        return "<unparseable-uri>"


# -------------------------------------------------------------------------
# Core factory with caching
# -------------------------------------------------------------------------
def get_redis_client() -> Redis[Any] | None:
    """
    Returns a cached Redis client if available, otherwise creates one.
    """
    # Explicit CLI/migration guard
    if os.environ.get("DISABLE_REDIS"):
        logger.info("DISABLE_REDIS set; skipping Redis client creation.")
        return None

    # Prefer an already-cached client attached to the Flask app context
    if has_app_context():
        cached = getattr(current_app, "redis_client", None)
        if cached is not None:
            return cast(Any, cached)

    raw_url = os.getenv("REDIS_STORAGE_URI", "").strip()
    if os.environ.get("FLASK_ENV") == "testing" and not raw_url:
        logger.debug(
            "Testing environment with no REDIS_STORAGE_URI; skipping Redis client creation."
        )
        return None

    if not raw_url:
        logger.debug("REDIS_STORAGE_URI not set; get_redis_client returning None.")
        return None

    url, tls_enabled = _normalize_redis_uri(raw_url)

    kwargs: dict[str, Any] = {
        "decode_responses": True,
        "socket_connect_timeout": (
            current_app.config.get("REDIS_CONNECT_TIMEOUT", 5)
            if has_app_context()
            else int(os.getenv("REDIS_CONNECT_TIMEOUT", 5))
        ),
        "socket_timeout": (
            current_app.config.get("REDIS_SOCKET_TIMEOUT", 5)
            if has_app_context()
            else int(os.getenv("REDIS_SOCKET_TIMEOUT", 5))
        ),
        "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
    }

    try:
        client = Redis.from_url(url, **kwargs)

        try:
            client.ping()
        except Exception as ping_exc:
            REDIS_CONNECT_FAILURES_COUNTER.inc()
            logger.warning("Redis ping failed for %s: %s", _masked_endpoint(url), ping_exc)
            try:
                ttl_emit(
                    key=REDIS_PING_KEY,
                    status=f"ping_error:{ping_exc}",
                    ttl=REDIS_FAIL_TTL,
                )
            except Exception:
                pass
            return None

        logger.info(
            "🟢 Redis ping successful—client checked out. endpoint=%s tls=%s",
            _masked_endpoint(url),
            tls_enabled,
        )
        try:
            ttl_emit(
                key=REDIS_PING_SUCCESS_KEY,
                status="success",
                ttl=REDIS_PING_TTL,
                client=client,
            )
            ttl_emit(
                key=REDIS_PING_SUCCESS_TS_KEY,
                status=_get_utc_timestamp(),
                ttl=REDIS_PING_TTL,
                client=client,
            )
            flushed = flush_emit_queue(client)
            logger.info("Flushed %d queued TTL emits.", flushed)
            ttl_emit(
                key=REDIS_QUEUE_FLUSH_KEY,
                status="success",
                ttl=REDIS_QUEUE_FLUSH_TTL,
                client=client,
            )
            ttl_emit(key=REDIS_PING_KEY, status="success", ttl=REDIS_PING_TTL, client=client)
        except Exception:
            logger.debug("Best-effort telemetry/flush failed (continuing).", exc_info=True)

        if has_app_context():
            current_app.redis_client = client

        return client

    except TypeError as te:
        REDIS_CONNECT_FAILURES_COUNTER.inc()
        logger.error(
            "Redis TypeError during connect (likely ssl kwarg issue): %s",
            te,
            exc_info=True,
        )
        try:
            ttl_emit(key=REDIS_PING_KEY, status=f"type_error:{te}", ttl=REDIS_FAIL_TTL)
        except Exception:
            pass
        return None

    except Exception as e:
        REDIS_CONNECT_FAILURES_COUNTER.inc()
        logger.error(
            "Redis connection/ping failed for %s: %s",
            _masked_endpoint(raw_url),
            e,
            exc_info=True,
        )
        try:
            ttl_emit(key=REDIS_PING_KEY, status=f"error:{e}", ttl=REDIS_FAIL_TTL)
        except Exception:
            pass
        return None


# -------------------------------------------------------------------------
# Dynamic Cluster Debug Flag Store (Prevents WSGI Worker Drift)
# -------------------------------------------------------------------------
def get_cluster_debug_flags() -> dict[str, Any]:
    """
    Retrieves dynamic debug flags from shared Redis state.
    Falls back to current_app.config if Redis is unreachable or unconfigured.
    """
    flags: dict[str, Any] = {}

    # 1. Start with process-local Flask config defaults
    if has_app_context():
        flags = {
            k: v
            for k, v in current_app.config.items()
            if k.isupper() and ("DEBUG" in k or "FLAG" in k)
        }

    # 2. Layer shared Redis overrides on top
    client = get_redis_client()
    if client:
        try:
            raw_hash = client.hgetall(REDIS_DEBUG_FLAGS_HASH)
            for k, v in raw_hash.items():
                key_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                val_str = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                try:
                    flags[key_str] = json.loads(val_str)
                except (json.JSONDecodeError, TypeError):
                    flags[key_str] = val_str
        except Exception as exc:
            logger.warning(
                "Redis flag lookup failed, relying on local config fallback: %s", exc
            )

    return flags


def set_cluster_debug_flags(updates: dict[str, Any]) -> dict[str, Any]:
    """
    Persists debug flag mutations into shared Redis storage and updates process config.
    Returns the dictionary of successfully applied flag key-value pairs.
    """
    client = get_redis_client()
    applied: dict[str, Any] = {}

    for key, value in updates.items():
        # Update current process memory if inside Flask app context
        if has_app_context():
            current_app.config[key] = value
        applied[key] = value

        # Sync across WSGI workers via Redis Hash
        if client:
            try:
                serialized = json.dumps(value)
                client.hset(REDIS_DEBUG_FLAGS_HASH, key, serialized)
            except Exception as exc:
                logger.warning(
                    "Failed to synchronize debug flag '%s' across Redis: %s", key, exc
                )

    return applied


# -------------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------------
def set_job_status(job_id: str, status: str, data: dict | None = None, ttl: int = 3600) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.setex(job_id, ttl, json.dumps({"status": status, "data": data or {}}))
    except Exception as e:
        logger.error("Failed to set job status for %s: %s", job_id, e, exc_info=True)


def get_job_status(job_id: str) -> dict[str, Any] | None:
    client = get_redis_client()
    if not client:
        return None
    try:
        raw = client.get(job_id)
        return cast(dict[str, Any], json.loads(raw)) if raw else None
    except Exception as e:
        logger.error("Failed to get job status for %s: %s", job_id, e, exc_info=True)
        return None


def increment_progress(blast_id: str, field: str) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.hincrby(f"dispute:progress:{blast_id}", field, 1)
    except Exception as e:
        logger.error("Failed to increment progress for %s: %s", blast_id, e, exc_info=True)


def init_progress(blast_id: str, total: int) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.hset(f"dispute:progress:{blast_id}", mapping={"total": total, "sent": 0})
    except Exception as e:
        logger.error("Failed to initialize progress for %s: %s", blast_id, e, exc_info=True)


def call_reflector_ai(payload: dict) -> dict[str, Any]:
    if not has_app_context():
        logger.error("ReflectorAI call requires a Flask app context.")
        return {"error": "No application context"}
    endpoint = current_app.config.get("REFLECTORAI_API_ENDPOINT")
    api_key = current_app.config.get("REFLECTORAI_API_KEY")
    if not endpoint or not api_key:
        current_app.logger.error("ReflectorAI API not configured.")
        return {"error": "API not configured"}
    try:
        resp = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        try:
            return cast(dict[str, Any], resp.json())
        except ValueError:
            current_app.logger.error("ReflectorAI returned non‑JSON response")
            return {"error": "Invalid JSON from ReflectorAI"}
    except requests.RequestException as exc:
        current_app.logger.error("ReflectorAI API call failed: %s", exc)
        return {"error": "Failed to call ReflectorAI API"}


# -------------------------------------------------------------------------
# Log retrieval helper for cockpit tiles
# -------------------------------------------------------------------------
def get_recent_logs(key: str, lines: int = 200) -> list[str]:
    """
    Retrieve recent log lines stored in Redis under a given key.
    Expects logs to be stored as a Redis list (LPUSH / RPUSH).
    Returns newest → oldest.
    """
    client = get_redis_client()
    if not client:
        return []

    try:
        raw = client.lrange(key, -lines, -1)
        return [
            (item.decode("utf-8", errors="ignore") if isinstance(item, bytes) else str(item))
            for item in raw
        ]
    except Exception as e:
        logger.error("Failed to retrieve logs for key %s: %s", key, e, exc_info=True)
        return []