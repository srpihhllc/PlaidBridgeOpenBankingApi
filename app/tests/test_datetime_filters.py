from datetime import UTC, datetime, timedelta

from flask import Flask

from app.filters.datetime_filters import (
    _coerce_datetime_utc,
    datetimeformat,
    fmt_date,
    fmt_datetime,
    fmt_iso_utc,
    fmt_time,
    register_datetime_filters,
    time_since,
    timeago,
    timeago_any,
)


def test_coerce_datetime_invalid_values():
    assert _coerce_datetime_utc(None) is None
    assert _coerce_datetime_utc("") is None
    assert _coerce_datetime_utc("   ") is None
    assert _coerce_datetime_utc("not-a-date") is None
    assert _coerce_datetime_utc(object()) is None


def test_coerce_epoch_values():
    result = _coerce_datetime_utc(0)

    assert result == datetime(1970, 1, 1, tzinfo=UTC)


def test_coerce_epoch_failure():
    assert _coerce_datetime_utc(float("inf")) is None


def test_coerce_naive_datetime_as_utc():
    value = datetime(2024, 1, 2, 3, 4, 5)

    result = _coerce_datetime_utc(value)

    assert result == value.replace(tzinfo=UTC)


def test_coerce_aware_datetime_to_utc():
    value = datetime(
        2024,
        1,
        2,
        3,
        4,
        5,
        tzinfo=__import__("datetime").timezone(timedelta(hours=-5)),
    )

    result = _coerce_datetime_utc(value)

    assert result == datetime(2024, 1, 2, 8, 4, 5, tzinfo=UTC)


def test_coerce_iso_strings():
    assert _coerce_datetime_utc("2024-01-02T03:04:05Z") == datetime(
        2024, 1, 2, 3, 4, 5, tzinfo=UTC
    )

    assert _coerce_datetime_utc("2024-01-02T03:04:05") == datetime(
        2024, 1, 2, 3, 4, 5, tzinfo=UTC
    )


def test_timeago_seconds_minutes_hours_and_days():
    assert timeago(datetime.now(UTC) - timedelta(seconds=20)).endswith("s ago")
    assert timeago(datetime.now(UTC) - timedelta(minutes=5)).endswith("m ago")
    assert timeago(datetime.now(UTC) - timedelta(hours=2)).endswith("h ago")
    assert timeago(datetime.now(UTC) - timedelta(days=3)).endswith("d ago")


def test_timeago_future_value():
    result = timeago(datetime.now(UTC) + timedelta(minutes=5))

    assert result.startswith("in ")
    assert result.endswith("m")


def test_timeago_invalid_value():
    assert timeago(None) == ""
    assert timeago("invalid") == ""


def test_timeago_any_alias():
    value = datetime.now(UTC) - timedelta(minutes=2)

    assert timeago_any(value) == timeago(value)


def test_time_since_all_ranges():
    assert time_since(datetime.now(UTC)) == "just now"
    assert time_since(datetime.now(UTC) - timedelta(minutes=1)) == "1 minute"
    assert time_since(datetime.now(UTC) - timedelta(minutes=2)) == "2 minutes"
    assert time_since(datetime.now(UTC) - timedelta(hours=1)) == "1 hour"
    assert time_since(datetime.now(UTC) - timedelta(hours=2)) == "2 hours"
    assert time_since(datetime.now(UTC) - timedelta(days=1)) == "1 day"
    assert time_since(datetime.now(UTC) - timedelta(days=2)) == "2 days"
    assert time_since(datetime.now(UTC) - timedelta(days=60)) == "2 months"
    assert time_since(datetime.now(UTC) - timedelta(days=365)) == "1 year"
    assert time_since(None) == ""


def test_formatting_helpers():
    value = "2024-01-02T03:04:05Z"

    assert datetimeformat(value, "%Y/%m/%d") == "2024/01/02"
    assert fmt_iso_utc(value) == "2024-01-02T03:04:05Z"
    assert fmt_datetime(value, "UTC", "%Y-%m-%d %H:%M:%S") == "2024-01-02 03:04:05"
    assert fmt_date(value) == "2024-01-02"
    assert fmt_time(value) == "03:04:05"


def test_formatting_invalid_values():
    assert datetimeformat(None) == ""
    assert fmt_iso_utc(None) == ""
    assert fmt_datetime(None) == ""
    assert fmt_date(None) == ""
    assert fmt_time(None) == ""


def test_formatting_timezone_and_invalid_timezone():
    value = "2024-01-02T03:04:05Z"

    assert fmt_datetime(
        value,
        "America/Chicago",
        "%Y-%m-%d %H:%M:%S",
    ).startswith("2024-01-01")

    # Invalid timezone falls back to UTC.
    assert fmt_datetime(
        value,
        "Not/ARealTimezone",
        "%Y-%m-%d %H:%M:%S",
    ) == "2024-01-02 03:04:05"


def test_formatting_invalid_format():
    assert fmt_datetime(
        "2024-01-02T03:04:05Z",
        fmt=None,
    ) == ""


def test_register_datetime_filters():
    app = Flask(__name__)

    register_datetime_filters(app)

    expected_filters = {
        "timeago": timeago,
        "timeago_any": timeago_any,
        "datetimeformat": datetimeformat,
        "time_since": time_since,
        "fmt_iso_utc": fmt_iso_utc,
        "fmt_datetime": fmt_datetime,
        "fmt_date": fmt_date,
        "fmt_time": fmt_time,
    }

    for name, function in expected_filters.items():
        assert app.jinja_env.filters[name] is function