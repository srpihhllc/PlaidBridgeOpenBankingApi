# =============================================================================
# FILE: app/workers/sync_worker.py
# DESCRIPTION:
#   Redis-backed worker for Plaid transaction synchronization.
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any, cast

from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REDIS_LIST_KEY = os.getenv("WORKER_SYNC_LIST_KEY", "sync:jobs")
POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "1.0"))
BLPOP_TIMEOUT = 5

AppFactory = Callable[[], Any]


def _load_app_factory() -> AppFactory | None:
    """Import the Flask application factory when available."""
    try:
        from app import create_app
    except ImportError:
        logger.exception("Unable to import the application factory")
        return None

    return cast(AppFactory, create_app)


create_app = _load_app_factory()


def process_job(job_payload: dict[str, Any]) -> int:
    """Sync Plaid transactions for a stored Plaid item."""
    from app.models.plaid_item import PlaidItem
    from app.services.transaction_ingestion import (
        sync_user_transactions_from_plaid,
    )
    from app.utils.plaid_crypto import decrypt_token

    nested_payload = job_payload.get("payload")
    data = (
        nested_payload
        if isinstance(nested_payload, dict)
        else job_payload
    )

    job_type = data.get("type") or job_payload.get("type")
    user_id = job_payload.get("user_id") or data.get("user_id")
    plaid_item_id = data.get("plaid_item_id")

    if job_type != "plaid_transactions":
        raise ValueError("Unsupported sync job type")
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("Sync job has no valid user_id")
    if not isinstance(plaid_item_id, str) or not plaid_item_id:
        raise ValueError("Sync job has no valid plaid_item_id")

    item = PlaidItem.query.filter_by(
        user_id=user_id,
        plaid_item_id=plaid_item_id,
    ).first()
    if item is None:
        raise ValueError("Plaid item not found for this user")

    access_token = decrypt_token(item.plaid_access_token)
    inserted_count = sync_user_transactions_from_plaid(
        user_id=user_id,
        plaid_access_token=access_token,
    )

    logger.info(
        "Plaid transaction sync processed: job_id=%s inserted=%d",
        job_payload.get("job_id"),
        inserted_count,
    )
    return inserted_count


def _get_extension(app: Any, name: str) -> Any:
    """Read an extension from either a dict-like or object-like container."""
    extensions = getattr(app, "extensions", None)

    if extensions is None:
        return None

    if isinstance(extensions, dict):
        return extensions.get(name)

    return getattr(extensions, name, None)


def _get_redis_client(app: Any) -> Any:
    """Get Redis from the app, its extensions, or the configured helper."""
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
    """Decode a Redis BLPOP result into a dictionary payload."""
    raw = item[1] if isinstance(item, (list, tuple)) and len(item) == 2 else item

    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")

    try:
        payload: Any = json.loads(raw)
    except (TypeError, ValueError):
        return {"raw": raw}

    if isinstance(payload, dict):
        return cast(dict[str, Any], payload)

    return {"raw": payload}


def main(max_iterations: int | None = None) -> None:
    """Run the Redis worker loop."""
    if create_app is None:
        raise RuntimeError(
            "Application factory not importable; ensure app.create_app exists"
        )

    app = create_app()
    redis_client = _get_redis_client(app)

    if redis_client is None:
        raise RuntimeError(
            "Redis client unavailable; refusing to start a no-op sync worker"
        )

    logger.info(
        "Starting Plaid sync worker: mode=%s redis_available=True list=%s",
        os.getenv("MODE", "unknown"),
        REDIS_LIST_KEY,
    )

    iterations = 0

    try:
        while max_iterations is None or iterations < max_iterations:
            iterations += 1

            try:
                item = redis_client.blpop(
                    REDIS_LIST_KEY,
                    timeout=BLPOP_TIMEOUT,
                )
            except TypeError:
                # Compatibility with clients that do not accept a timeout.
                item = redis_client.blpop(REDIS_LIST_KEY)
            except (RedisTimeoutError, TimeoutError):
                logger.warning("Redis BLPOP timed out; continuing to poll")
                continue

            if not item:
                time.sleep(POLL_INTERVAL)
                continue

            payload = _decode_job(item)

            try:
                with app.app_context():
                    process_job(payload)
            except Exception:
                logger.exception(
                    "Sync job failed: job_id=%s",
                    payload.get("job_id"),
                )

    except KeyboardInterrupt:
        logger.info("Worker shutdown requested by KeyboardInterrupt")


if __name__ == "__main__":
    main()
