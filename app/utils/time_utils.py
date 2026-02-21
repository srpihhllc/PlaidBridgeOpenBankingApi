# app/utils/time_utils.py

from datetime import datetime


def time_since(ts):
    """Returns human-readable age like '5m ago' or '2h ago'"""
    delta = datetime.utcnow() - ts
    seconds = delta.total_seconds()
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    else:
        return f"{int(seconds // 86400)}d ago"


def safe_parse_timestamp(value):
    """
    Safely parse an ISO timestamp string into a datetime object.
    Returns datetime.min if parsing fails.
    """
    if not value:
        return datetime.min

    try:
        # Handle timestamps with or without Z suffix
        cleaned = value.replace("Z", "")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return datetime.min
