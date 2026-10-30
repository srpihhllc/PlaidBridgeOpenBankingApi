"""
Datetime filters for Jinja templates.

Usage (register in your app factory):
    from app.filters.datetime_filters import register_datetime_filters
    register_datetime_filters(flask_app)

Then in Jinja:
    {{ last_audit_epoch | timeago }}
    {{ last_audit_iso | datetimeformat('%Y-%m-%d') }}
    {{ created_at | time_since }}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

try:
    # Python 3.9+ standard library timezones
    from zoneinfo import ZoneInfo
    HAS_ZONEINFO = True
except Exception:  # pragma: no cover
    HAS_ZONEINFO = False
    ZoneInfo = None  # type: ignore[assignment, misc]


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


def timeago(value: DateLike) -> str:
    """
    Render a compact relative time from an epoch, ISO string, or datetime.
    """
    dt = _coerce_datetime_utc(value)

    if dt is None:
        return ""

    seconds = int((datetime.now(UTC) - dt).total_seconds())

    if seconds < 0:
        seconds = abs(seconds)
        prefix = "in "
        suffix = ""
    else:
        prefix = ""
        suffix = " ago"

    if seconds < 60:
        return f"{prefix}{seconds}s{suffix}"

    minutes = seconds // 60
    if minutes < 60:
        return f"{prefix}{minutes}m{suffix}"

    hours = minutes // 60
    if hours < 24:
        return f"{prefix}{hours}h{suffix}"

    days = hours // 24
    return f"{prefix}{days}d{suffix}"


def timeago_any(value: DateLike) -> str:
    """
    Alias for timeago for backwards compatibility.
    """
    return timeago(value)


def datetimeformat(
    value: DateLike,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    Format a date-like value in UTC using the specified strftime format.
    """
    return fmt_datetime(value, "UTC", fmt)


def time_since(value: DateLike) -> str:
    """
    Render a readable elapsed time without the word 'ago'.
    Useful for UI templates that manually append 'ago' or format offsets.
    """
    dt = _coerce_datetime_utc(value)
    if dt is None:
        return ""

    seconds = max(0, int((datetime.now(UTC) - dt).total_seconds()))

    if seconds < 60:
        return "just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''}"

    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''}"

    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''}"

    years = months // 12
    return f"{years} year{'s' if years != 1 else ''}"


def fmt_iso_utc(value: DateLike) -> str:
    """
    Format any date-like value as ISO8601 in UTC.
    Returns '' on invalid input.
    """
    dt = _coerce_datetime_utc(value)
    return dt.isoformat().replace("+00:00", "Z") if dt else ""


def fmt_datetime(
    value: DateLike, tz_name: str = "UTC", fmt: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    Format a date-like value into the given timezone and strftime format.
    - tz_name: IANA timezone (e.g., 'America/Chicago'). If ZoneInfo unavailable, falls back to UTC.
    Returns '' on invalid input.
    """
    dt_utc = _coerce_datetime_utc(value)
    if dt_utc is None:
        return ""
    if HAS_ZONEINFO and ZoneInfo is not None and tz_name:
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


def fmt_date(
    value: DateLike, tz_name: str = "UTC", fmt: str = "%Y-%m-%d"
) -> str:
    """
    Format only the date portion in the given timezone.
    """
    return fmt_datetime(value, tz_name, fmt)


def fmt_time(
    value: DateLike, tz_name: str = "UTC", fmt: str = "%H:%M:%S"
) -> str:
    """
    Format only the time portion in the given timezone.
    """
    return fmt_datetime(value, tz_name, fmt)


def register_datetime_filters(app: Any) -> None:
    """
    Register all datetime filters on the provided Flask app instance.
    Call from within create_app() after constructing the Flask app instance.
    """
    app.jinja_env.filters["timeago"] = timeago
    app.jinja_env.filters["timeago_any"] = timeago_any
    app.jinja_env.filters["datetimeformat"] = datetimeformat
    app.jinja_env.filters["time_since"] = time_since
    app.jinja_env.filters["fmt_iso_utc"] = fmt_iso_utc
    app.jinja_env.filters["fmt_datetime"] = fmt_datetime
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["fmt_time"] = fmt_time