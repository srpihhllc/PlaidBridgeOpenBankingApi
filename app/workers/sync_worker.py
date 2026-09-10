# app/workers/sync_worker.py

"""
Minimal Redis-backed sync worker.

The worker initializes the Flask application, obtains a Redis client, and
processes JSON job payloads from the Redis list configured by
WORKER_SYNC_LIST_KEY.

For production, call main() with no arguments.

For tests or controlled execution, pass max_iterations to limit the number
of polling iterations.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

try:
    from app import create_app
except Exception:  # pragma: no cover - exercised only when imports fail
    create_app = None


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REDIS_LIST_KEY = os.getenv("WORKER_SYNC_LIST_KEY", "sync:jobs")
POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "1.0"))


def process_job(job_payload: dict[str, Any]) -> None:
    """
    Process one decoded job payload.

    Replace this placeholder with the real synchronization logic.
    """
    logger.info(
        "Processing job: id=%s type=%s",
        job_payload.get("job_id"),
        job_payload.get("type"),
    )

    # TODO: replace with real handler code:
    # - validate payload
    # - call connector adapters
    # - persist normalized data
    # - emit audit logs and metrics

    time.sleep(0.1)


def _get_extension(app: Any, name: str) -> Any:
    """Read an extension from either a dict-like or object-like container."""
    extensions = getattr(app, "extensions", None)

    if extensions is None:
        return None

    if isinstance(extensions, dict):
        return extensions.get(name)

    return getattr(extensions, name, None)


def _get_redis_client(app: Any) -> Any:
    """
    Get Redis from the Flask app, then fall back to app.extensions.

    Finally, try the optional app.extensions.get_redis_client helper.
    """
    redis_client = getattr(app, "redis_client", None)

    if redis_client is not None:
        return redis_client

    redis_client = _get_extension(app, "redis_client")

    if redis_client is not None:
        return redis_client

    try:
        from app.extensions import get_redis_client
    except (ImportError, AttributeError):
        return None

    try:
        return get_redis_client()
    except Exception:
        logger.exception("Unable to initialize Redis client")
        return None


def _decode_job(item: Any) -> dict[str, Any]:
    """
    Convert a Redis BLPOP result into a dictionary payload.

    redis-py normally returns (key, value), where values may be bytes.
    Invalid JSON is preserved under the 'raw' key.
    """
    if isinstance(item, (list, tuple)) and len(item) == 2:
        raw = item[1]
    else:
        raw = item

    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {"raw": raw}

    if isinstance(payload, dict):
        return payload

    return {"raw": payload}


def main(max_iterations: int | None = None) -> None:
    """
    Start the worker loop.

    Args:
        max_iterations: Optional maximum number of polling iterations.
            None means run indefinitely.
    """
    if create_app is None:
        raise RuntimeError(
            "Application factory not importable; ensure the package is "
            "on PYTHONPATH and app.create_app exists"
        )

    app = create_app()
    redis_client = _get_redis_client(app)

    logger.info(
        "Starting minimal sync worker: mode=%s redis_available=%s",
        os.getenv("MODE", "unknown"),
        bool(redis_client),
    )

    iterations = 0

    if redis_client is None:
        logger.warning(
            "No Redis client available; worker will run a no-op loop. "
            "Set REDIS_URL or Redis configuration to enable queue processing."
        )

        try:
            while max_iterations is None or iterations < max_iterations:
                iterations += 1
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Worker stopped by KeyboardInterrupt")

        return

    try:
        while max_iterations is None or iterations < max_iterations:
            iterations += 1

            try:
                item = redis_client.blpop(REDIS_LIST_KEY, timeout=5)
            except TypeError:
                # Compatibility with clients that do not accept timeout.
                item = None

            if not item:
                time.sleep(POLL_INTERVAL)
                continue

            payload = _decode_job(item)

            try:
                process_job(payload)
            except Exception:
                logger.exception("Job processing failed")

    except KeyboardInterrupt:
        logger.info("Worker shutdown requested by KeyboardInterrupt")
    except Exception:
        logger.exception("Worker terminated unexpectedly")


if __name__ == "__main__":
    main()
