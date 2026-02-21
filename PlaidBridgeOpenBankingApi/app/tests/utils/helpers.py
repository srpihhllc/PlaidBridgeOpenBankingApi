# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/utils/helpers.py

# =============================================================================
# FILE: app/tests/utils/helpers.py
# DESCRIPTION: Helper functions for asserting telemetry events in Redis (test-only).
#              Exposes a small passthrough to the application's Redis getter
#              and a clear helper so tests can deterministically reset telemetry.
# =============================================================================

import json

from app.utils.redis_utils import get_redis_client as _get_redis_client


def get_redis_client():
    """
    Test-facing passthrough to the app's Redis client factory.
    Keeps tests decoupled from the implementation location while ensuring
    the same client instance is returned as the application uses.
    """
    return _get_redis_client()


def clear_identity_events() -> None:
    """
    Best-effort removal of the identity events stream from Redis.
    Tests should call this (or use an autouse fixture) to avoid cross-test noise.
    """
    rc = get_redis_client()
    if not rc:
        return
    try:
        rc.delete("identity_events_stream")
    except Exception:
        # Swallow any Redis error on cleanup; tests remain best-effort deterministic.
        return


def fetch_identity_events(limit: int = 50) -> list[dict]:
    """
    Read up to `limit` events from the identity events stream in Redis.
    Returns an empty list if Redis is unavailable.
    Each event is returned as a decoded JSON object; malformed entries are skipped.
    """
    client = get_redis_client()
    if not client:
        return []
    try:
        raw = client.lrange("identity_events_stream", 0, limit - 1)
    except Exception:
        return []
    events: list[dict] = []
    for item in raw:
        try:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            events.append(json.loads(item))
        except Exception:
            # Ignore malformed entries in the stream for test robustness
            continue
    return events


def assert_event_exists(event_type: str, user_id: int | None = None) -> bool:
    """
    Return True if an event matching event_type (and optional user_id) exists.
    Designed for use in test assertions (tests should call assert_event_with_retry
    in case events are emitted asynchronously).
    """
    events = fetch_identity_events()
    for ev in events:
        if ev.get("event_type") == event_type:
            if user_id is None or ev.get("user_id") == user_id:
                return True
    return False
