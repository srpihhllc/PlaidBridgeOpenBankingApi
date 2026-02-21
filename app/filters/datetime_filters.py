# app/filters/datetime_filters.py

"""
Datetime filters for Jinja templates.

Usage (register in your app factory):
    from app.filters.datetime_filters import register_datetime_filters
    register_datetime_filters(flask_app)

Then in Jinja:
    {{ last_audit_epoch | timeago }}
    {{ some_iso_string | fmt_datetime('America/Chicago', '%Y-%m-%d %H:%M') }}
    {{ some_epoch | fmt_date('America/Chicago') }}
"""

from __future__ import annotations

from datetime import UTC, datetime

try:
    # Python 3.9+ standard library timezones
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # Fallback if not available; tz features will assume UTC


Number = int | float
DateLike = datetime | str | Number


def _coerce_datetime_utc(value: DateLike) -> datetime | None:
    """
    Coerce input (epoch seconds, ISO string, or datetime) to an aware UTC datetime.
    - Epoch (int/float): treated as seconds since epoch.
    - ISO string: parsed; 'Z' suffix treated as UTC.
    - datetime:
        - naive -> assume UTC
        - aware -> converted to UTC
    Returns None on failure.
    """
    if value is None:
        return None

    # Epoch number
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except Exception:
            return None

    # Datetime
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    # ISO string
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # Support 'Z' suffix (UTC)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    return None


def timeago(epoch: Number) -> str:
    """
    Render a compact relative time from epoch seconds
    (e.g., '12s ago', '5m ago', '3h ago', '2d ago').
    Returns '' on invalid input.
    """
    try:
        ts = int(epoch)
    except Exception:
        return ""
    now = datetime.now(UTC)
    then = datetime.fromtimestamp(ts, tz=UTC)
    delta = now - then
    seconds = int(delta.total_seconds())
    if seconds < 0:
        # Future timestamp; show 'in Xs/min/h/d'
        seconds = abs(seconds)
        if seconds < 60:
            return f"in {seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"in {minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"in {hours}h"
        days = hours // 24
        return f"in {days}d"

    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def timeago_any(value: DateLike) -> str:
    """
    Like timeago, but accepts epoch, ISO string, or datetime.
    Returns '' on invalid input.
    """
    dt = _coerce_datetime_utc(value)
    if dt is None:
        return ""
    return timeago(dt.timestamp())


def fmt_iso_utc(value: DateLike) -> str:
    """
    Format any date-like value as ISO8601 in UTC.
    Returns '' on invalid input.
    """
    dt = _coerce_datetime_utc(value)
    return dt.isoformat().replace("+00:00", "Z") if dt else ""


def fmt_datetime(value: DateLike, tz_name: str = "UTC", fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a date-like value into the given timezone and strftime format.
    - tz_name: IANA timezone (e.g., 'America/Chicago'). If ZoneInfo unavailable, falls back to UTC.
    Returns '' on invalid input.
    """
    dt_utc = _coerce_datetime_utc(value)
    if dt_utc is None:
        return ""
    if ZoneInfo and tz_name:
        try:
            dt_local = dt_utc.astimezone(ZoneInfo(tz_name))
        except Exception:
            dt_local = dt_utc
    else:
        dt_local = dt_utc
    try:
        return dt_local.strftime(fmt)
    except Exception:
        return ""


def fmt_date(value: DateLike, tz_name: str = "UTC", fmt: str = "%Y-%m-%d") -> str:
    """
    Format only the date portion in the given timezone.
    """
    return fmt_datetime(value, tz_name, fmt)


def fmt_time(value: DateLike, tz_name: str = "UTC", fmt: str = "%H:%M:%S") -> str:
    """
    Format only the time portion in the given timezone.
    """
    return fmt_datetime(value, tz_name, fmt)


def register_datetime_filters(app) -> None:
    """
    Register all filters on the provided Flask app.
    Call from within your create_app() after the app is constructed.
    """
    app.jinja_env.filters["timeago"] = timeago
    app.jinja_env.filters["timeago_any"] = timeago_any
    app.jinja_env.filters["fmt_iso_utc"] = fmt_iso_utc
    app.jinja_env.filters["fmt_datetime"] = fmt_datetime
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["fmt_time"] = fmt_time
