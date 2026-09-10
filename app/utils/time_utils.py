# app/utils/time_utils.py

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    """Returns the current UTC timestamp formatted as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def time_since(ts: datetime) -> str:
    """
    Returns human-readable age like '5m ago' or '2h ago'.
    Handles both timezone-aware and naive datetime inputs seamlessly.
    """
    if ts is None:
        return "unknown"

    now = datetime.now(timezone.utc)

    # Convert naive timestamps to timezone-aware UTC to prevent offset type errors
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    delta = now - ts
    seconds = max(0, delta.total_seconds())

    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    else:
        return f"{int(seconds // 86400)}d ago"


def safe_parse_timestamp(value: str) -> datetime:
    """
    Safely parse an ISO timestamp string into a timezone-aware datetime object.
    Returns datetime.min (aware) if parsing fails or input is empty.
    """
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        # datetime.fromisoformat handles ISO-8601 strings natively in Python 3.11+
        # replacing 'Z' with UTC offset ensures proper timezone awareness across versions
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)
