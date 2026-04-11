# =============================================================================
# FILE: app/tests/test_oauth_callback.py
# DESCRIPTION: Tests for Google OAuth callback flows against unified oauth_routes.
# =============================================================================

import pytest
from flask import url_for
from requests.exceptions import HTTPError, Timeout

from app import create_app
from app.extensions import db
from app.models import User
from app.models.trace_events import TraceEvent


@pytest.fixture
def app():
    """Provide a Flask app with in-memory SQLite for testing Google OAuth callbacks."""
    application = create_app(env_name="testing")
    application.config.update(
        TESTING=False,  # use production-style callback path, not the TESTING short-circuit
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        GOOGLE_CLIENT_ID="test-client-id",
        GOOGLE_CLIENT_SECRET="test-client-secret",
        GOOGLE_REDIRECT_URI="http://localhost/oauth/callback/google",
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Provide a test client for the Flask app."""
    return app.test_client()


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def assert_events(expected_types, ordered=False):
    """Assert that TraceEvent rows match expected event types."""
    with db.session.no_autoflush:
        q = TraceEvent.query.order_by(TraceEvent.id) if ordered else TraceEvent.query
        events = q.all()
        types = [e.event_type for e in events]
        if ordered:
            assert types == expected_types
        else:
            assert set(types) == set(expected_types)
            assert len(types) == len(expected_types)
        return events


def assert_user_created(email="test@example.com"):
    """Assert that a user with the given email exists."""
    user = User.query.filter_by(email=email).first()
    assert user is not None
    return user


def assert_no_user():
    """Assert that no users exist in the database."""
    assert User.query.count() == 0


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------
def test_google_success(monkeypatch, client, app):
    """Simulate a successful Google OAuth callback."""

    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "fake-token", "id_token": "fake-id"}

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)

    def mock_get(url, headers=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "email": "test@example.com",
                    "sub": "123",
                    "name": "Tester",
                }

        return Resp()

    monkeypatch.setattr("requests.get", mock_get)

    resp = client.get(url_for("oauth.callback_google", code="abc123"))
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/dashboard")

    with app.app_context():
        assert_user_created()
        assert_events(["OAUTH_LOGIN_SUCCESS", "SESSION_ESTABLISHED"], ordered=True)


@pytest.mark.parametrize(
    "mock_exception",
    [
        pytest.param(Timeout("Read timed out."), id="timeout"),
        pytest.param(
            HTTPError("500 Server Error: Internal Server Error"),
            id="http-error-500",
        ),
        pytest.param(Exception("Malformed JSON response."), id="malformed-json"),
    ],
)
def test_google_token_failure_variants(monkeypatch, client, app, mock_exception):
    """Simulate different token exchange failure modes."""

    def mock_post(url, data=None, timeout=10):
        raise mock_exception

    monkeypatch.setattr("requests.post", mock_post)

    resp = client.get(url_for("oauth.callback_google", code="abc123"))
    assert resp.status_code == 502

    with app.app_context():
        events = assert_events(["OAUTH_TOKEN_ERROR"])
        assert_no_user()
        assert mock_exception.args[0] in events[0].details.get("error", "")


def test_google_profile_missing_email(monkeypatch, client, app):
    """Simulate Google profile response without email."""

    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "fake-token"}

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)

    def mock_get(url, headers=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"sub": "123"}

        return Resp()

    monkeypatch.setattr("requests.get", mock_get)

    resp = client.get(url_for("oauth.callback_google", code="abc123"))
    assert resp.status_code == 401

    with app.app_context():
        events = assert_events(["OAUTH_LOGIN_FAILURE"])
        assert_no_user()
        assert "Profile payload missing email" in events[0].details.get("reason", "")


def test_google_profile_error_invalid_id_token(monkeypatch, client, app):
    """Simulate an invalid ID token during Google OAuth callback (profile fetch error)."""

    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "fake-token", "id_token": "bad-id-token"}

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)

    def mock_get(url, headers=None, timeout=10):
        # In the unified provider, ID token verification happens inside fetch_profile,
        # so we simulate that by raising from the profile call.
        raise Exception("ID token validation failed")

    monkeypatch.setattr("requests.get", mock_get)

    resp = client.get(url_for("oauth.callback_google", code="abc123"))
    assert resp.status_code == 502  # profile fetch failure path

    with app.app_context():
        events = assert_events(["OAUTH_PROFILE_ERROR"])
        assert_no_user()
        assert "ID token validation failed" in events[0].details.get("error", "")


@pytest.mark.parametrize(
    "profile_payload, missing_fields",
    [
        pytest.param({"email": "test@example.com"}, ["sub", "name"], id="missing-sub-and-name"),
        pytest.param({"email": "test@example.com", "sub": "123"}, ["name"], id="missing-name"),
        pytest.param({"email": "test@example.com", "name": "User"}, ["sub"], id="missing-sub"),
    ],
)
def test_google_profile_incomplete_variants(monkeypatch, client, app, profile_payload, missing_fields):
    """Simulate Google profile responses missing optional fields."""

    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "fake-token", "id_token": "fake-id"}

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)

    def mock_get(url, headers=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return profile_payload

        return Resp()

    monkeypatch.setattr("requests.get", mock_get)

    resp = client.get(url_for("oauth.callback_google", code="abc123"))
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/dashboard")

    with app.app_context():
        assert_user_created()
        events = assert_events(
            ["OAUTH_PROFILE_INCOMPLETE", "OAUTH_LOGIN_SUCCESS", "SESSION_ESTABLISHED"],
            ordered=True,
        )
        reason = events[0].details.get("reason", "")
        for field in missing_fields:
            assert field in reason

