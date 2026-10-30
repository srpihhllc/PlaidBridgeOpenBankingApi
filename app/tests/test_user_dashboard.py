# app/tests/test_user_dashboard.py

from unittest.mock import MagicMock

import pytest

from app.models.user_dashboard import UserDashboard


# ----------------------------------------------------------------------
# Default Settings & Factory Tests
# ----------------------------------------------------------------------


def test_default_settings():
    settings = UserDashboard.default_settings()

    assert settings == {
        "layout": "two_column",
        "theme": "light",
        "show_todo_tile": True,
        "show_today_widget": True,
        "show_balance_tile": True,
        "show_activity_tile": True,
        "todo_sort": "created",
        "todo_filter": "all",
        "default_priority": "normal",
        "default_category": None,
    }


def test_create_for_user():
    dashboard = UserDashboard.create_for_user("user-123")

    assert dashboard.user_id == "user-123"
    assert dashboard.settings == UserDashboard.default_settings()


# ----------------------------------------------------------------------
# Settings Accessors Tests
# ----------------------------------------------------------------------


def test_get_setting_returns_default_when_settings_are_missing():
    dashboard = UserDashboard(user_id="user-123")
    dashboard.settings = None

    assert dashboard.get_setting("theme") is None
    assert dashboard.get_setting("theme", "dark") == "dark"


def test_get_setting_returns_existing_value():
    dashboard = UserDashboard(
        user_id="user-123",
        settings={"theme": "dark"},
    )

    assert dashboard.get_setting("theme") == "dark"
    assert dashboard.get_setting("missing", "fallback") == "fallback"


def test_set_setting_initializes_missing_settings():
    dashboard = UserDashboard(user_id="user-123")
    dashboard.settings = None

    result = dashboard.set_setting("theme", "dark")

    assert result == {"theme": "dark"}
    assert dashboard.settings == {"theme": "dark"}


def test_set_setting_updates_existing_settings():
    dashboard = UserDashboard(
        user_id="user-123",
        settings={"theme": "light"},
    )

    result = dashboard.set_setting("theme", "dark")

    assert result == {"theme": "dark"}
    assert dashboard.settings == {"theme": "dark"}


# ----------------------------------------------------------------------
# Widget Helpers Tests
# ----------------------------------------------------------------------


def test_enable_widget():
    dashboard = UserDashboard(user_id="user-123")

    result = dashboard.enable_widget("show_balance_tile")

    assert result == {"show_balance_tile": True}
    assert dashboard.get_setting("show_balance_tile") is True


def test_disable_widget():
    dashboard = UserDashboard(user_id="user-123")

    result = dashboard.disable_widget("show_balance_tile")

    assert result == {"show_balance_tile": False}
    assert dashboard.get_setting("show_balance_tile") is False


@pytest.mark.parametrize(
    ("initial_value", "expected_value"),
    [
        (None, True),
        (False, True),
        (True, False),
        (0, True),
        ("enabled", False),
    ],
)
def test_toggle_widget(initial_value, expected_value):
    dashboard = UserDashboard(
        user_id="user-123",
        settings=(
            {}
            if initial_value is None
            else {"show_balance_tile": initial_value}
        ),
    )

    result = dashboard.toggle_widget("show_balance_tile")

    assert result["show_balance_tile"] is expected_value


# ----------------------------------------------------------------------
# Persistence & Representation Tests
# ----------------------------------------------------------------------


def test_save_adds_and_commits(monkeypatch):
    dashboard = UserDashboard(
        user_id="user-123",
        settings={"theme": "dark"},
    )

    session = MagicMock()

    monkeypatch.setattr(
        "app.models.user_dashboard.db.session",
        session,
    )

    result = dashboard.save()

    assert result is dashboard
    session.add.assert_called_once_with(dashboard)
    session.commit.assert_called_once_with()


def test_repr_includes_user_and_layout():
    dashboard = UserDashboard(
        user_id="user-123",
        settings={"layout": "three_column"},
    )

    assert repr(dashboard) == (
        "<UserDashboard user_id=user-123 layout=three_column>"
    )


def test_repr_handles_missing_layout():
    dashboard = UserDashboard(
        user_id="user-123",
        settings=None,
    )

    assert repr(dashboard) == (
        "<UserDashboard user_id=user-123 layout=None>"
    )