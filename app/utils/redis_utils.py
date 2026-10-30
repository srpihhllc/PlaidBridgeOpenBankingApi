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
    from app.metrics import REDIS_CONNECT_FAILURES_COUNTER
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
    if not uri:
        return uri, False

    parsed = urlparse(uri)
    scheme = parsed.scheme
    if scheme.lower() == "redis+ssl":
        scheme = "rediss"

    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    promote_tls = q.get("ssl", "").lower() == "true"
    q.pop("ssl", "")

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
# Core factory with caching (Singleton)
# -------------------------------------------------------------------------
_REDIS_CLIENT: Redis | None = None


def get_redis_client() -> Redis | None:
    """
    Enterprise-grade Redis singleton.

    Characteristics:
    - Safe under Python 3.12.
    - Lazy initialization.
    - Cached globally.
    - Cached on Flask app object.
    - Graceful degradation.
    - Never raises to caller.
    """
    global _REDIS_CLIENT

    if os.getenv("DISABLE_REDIS"):
        logger.info("DISABLE_REDIS enabled; Redis disabled.")
        return None

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    if has_app_context():
        cached = getattr(current_app, "redis_client", None)
        if cached is not None:
            _REDIS_CLIENT = cast(Redis, cached)
            return _REDIS_CLIENT

    raw_url = (
        os.getenv("REDIS_URL")
        or os.getenv("REDIS_STORAGE_URI")
        or ""
    ).strip()

    if not raw_url:
        logger.info("Redis URL not configured.")
        return None

    try:
        url, tls_enabled = _normalize_redis_uri(raw_url)

        redis_client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=int(
                os.getenv("REDIS_CONNECT_TIMEOUT", "5")
            ),
            socket_timeout=int(
                os.getenv("REDIS_SOCKET_TIMEOUT", "5")
            ),
            max_connections=int(
                os.getenv("REDIS_MAX_CONNECTIONS", "20")
            ),
        )

        redis_client.ping()

        logger.info(
            "🟢 Redis ping successful. endpoint=%s tls=%s",
            _masked_endpoint(url),
            tls_enabled,
        )

        try:
            ttl_emit(
                key=REDIS_PING_SUCCESS_KEY,
                status="success",
                ttl=REDIS_PING_TTL,
                client=redis_client,
            )
            ttl_emit(
                key=REDIS_PING_SUCCESS_TS_KEY,
                status=_get_utc_timestamp(),
                ttl=REDIS_PING_TTL,
                client=redis_client,
            )
            flushed = flush_emit_queue(redis_client)
            logger.info("Flushed %d queued TTL emits.", flushed)
            ttl_emit(
                key=REDIS_QUEUE_FLUSH_KEY,
                status="success",
                ttl=REDIS_QUEUE_FLUSH_TTL,
                client=redis_client,
            )
            ttl_emit(
                key=REDIS_PING_KEY,
                status="success",
                ttl=REDIS_PING_TTL,
                client=redis_client,
            )
        except Exception:
            logger.debug("Telemetry emit failed.", exc_info=True)

        _REDIS_CLIENT = redis_client

        if has_app_context():
            current_app.redis_client = redis_client

        return redis_client

    except Exception as error:
        REDIS_CONNECT_FAILURES_COUNTER.inc()

        logger.error(
            "Redis initialization failed: %s",
            error,
            exc_info=True,
        )

        try:
            ttl_emit(
                key=REDIS_PING_KEY,
                status=f"error:{error}",
                ttl=REDIS_FAIL_TTL,
            )
        except Exception:
            pass

        return None


# -------------------------------------------------------------------------
# Dynamic Cluster Debug Flag Store
# -------------------------------------------------------------------------
def get_cluster_debug_flags() -> dict[str, Any]:
    flags: dict[str, Any] = {}

    if has_app_context():
        flags.update(
            {
                k: v
                for k, v in current_app.config.items()
                if "DEBUG" in k or "FLAG" in k
            }
        )

    client = get_redis_client()

    if client is None:
        return flags

    try:
        for k, v in client.hgetall(REDIS_DEBUG_FLAGS_HASH).items():
            try:
                flags[str(k)] = json.loads(v)
            except Exception:
                flags[str(k)] = v
    except Exception:
        logger.warning(
            "Redis debug-flag retrieval failed.",
            exc_info=True,
        )

    return flags


def set_cluster_debug_flags(updates: dict[str, Any]) -> dict[str, Any]:
    client = get_redis_client()
    applied: dict[str, Any] = {}

    for key, value in updates.items():
        if has_app_context():
            current_app.config[key] = value
        applied[key] = value

        if client:
            try:
                serialized = json.dumps(value)
                client.hset(REDIS_DEBUG_FLAGS_HASH, key, serialized)
            except Exception as exc:
                logger.warning(
                    "Failed to synchronize debug flag '%s' across Redis: %s",
                    key,
                    exc,
                )

    return applied


# -------------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------------
def set_job_status(
    job_id: str, status: str, data: dict[str, Any] | None = None, ttl: int = 3600
) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.setex(
            job_id, ttl, json.dumps({"status": status, "data": data or {}})
        )
    except Exception as e:
        logger.error(
            "Failed to set job status for %s: %s", job_id, e, exc_info=True
        )


def get_job_status(job_id: str) -> dict[str, Any] | None:
    client = get_redis_client()
    if not client:
        return None
    try:
        raw = client.get(job_id)
        return cast(dict[str, Any], json.loads(raw)) if raw else None
    except Exception as e:
        logger.error(
            "Failed to get job status for %s: %s", job_id, e, exc_info=True
        )
        return None


def increment_progress(blast_id: str, field: str) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.hincrby(f"dispute:progress:{blast_id}", field, 1)
    except Exception as e:
        logger.error(
            "Failed to increment progress for %s: %s",
            blast_id,
            e,
            exc_info=True,
        )


def init_progress(blast_id: str, total: int) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.hset(
            f"dispute:progress:{blast_id}", mapping={"total": total, "sent": 0}
        )
    except Exception as e:
        logger.error(
            "Failed to initialize progress for %s: %s",
            blast_id,
            e,
            exc_info=True,
        )


def call_reflector_ai(payload: dict[str, Any]) -> dict[str, Any]:
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
            timeout=(5, 10),
        )
        resp.raise_for_status()
        try:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                current_app.logger.error("ReflectorAI returned non-JSON content type: %s", content_type)
                return {"error": "Invalid response type from ReflectorAI"}
            return cast(dict[str, Any], resp.json())
        except ValueError:
            current_app.logger.error("ReflectorAI returned non‑JSON response")
            return {"error": "Invalid JSON from ReflectorAI"}
    except requests.RequestException as exc:
        current_app.logger.error("ReflectorAI API call failed: %s", exc)
        return {"error": "Failed to call ReflectorAI API"}


def get_recent_logs(key: str, lines: int = 200) -> list[str]:
    client = get_redis_client()
    if not client:
        return []

    try:
        raw = client.lrange(key, -lines, -1)
        return [
            (
                item.decode("utf-8", errors="ignore")
                if isinstance(item, bytes)
                else str(item)
            )
            for item in raw
        ]
    except Exception as e:
        logger.error(
            "Failed to retrieve logs for key %s: %s", key, e, exc_info=True
        )
        return []