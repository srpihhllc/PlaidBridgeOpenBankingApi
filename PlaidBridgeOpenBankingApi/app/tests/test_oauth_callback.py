# =============================================================================
# FILE: app/tests/test_oauth_callback.py
# DESCRIPTION: Tests for Google OAuth callback flows.
# =============================================================================

import pytest
from flask import url_for
from requests.exceptions import HTTPError, Timeout

from app import create_app, db
from app.models import User
from app.models.trace_events import TraceEvent


@pytest.fixture
def app():
    """Provide a Flask app with in-memory SQLite for testing."""
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with app.app_context():
        db.create_all()
        yield app
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
                return {"email": "test@example.com", "sub": "123", "name": "Tester"}

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
        pytest.param(HTTPError("500 Server Error: Internal Server Error"), id="http-error-500"),
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
        assert mock_exception.args[0] in events[0].details.get("error")


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
        assert "Profile payload missing email" in events[0].details.get("reason")


def test_google_invalid_id_token(monkeypatch, client, app):
    """Simulate an invalid ID token during Google OAuth callback."""

    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "fake-token", "id_token": "bad-id-token"}

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)

    def mock_get(url, headers=None, timeout=10):
        raise AssertionError("Profile endpoint should not be called when ID token is invalid")

    monkeypatch.setattr("requests.get", mock_get)

    def mock_verify(token, request, audience):
        raise Exception("Invalid ID token")

    monkeypatch.setattr("google.oauth2.id_token.verify_oauth2_token", mock_verify)

    resp = client.get(url_for("oauth.callback_google", code="abc123"))
    assert resp.status_code == 401

    with app.app_context():
        events = assert_events(["OAUTH_IDTOKEN_INVALID"])
        assert_no_user()
        assert "ID token validation failed" in events[0].details.get("reason")


@pytest.mark.parametrize(
    "profile_payload",
    [
        pytest.param({"email": "test@example.com"}, id="missing-sub-and-name"),
        pytest.param({"email": "test@example.com", "sub": "123"}, id="missing-name"),
        pytest.param({"email": "test@example.com", "name": "User"}, id="missing-sub"),
    ],
)
def test_google_profile_incomplete_variants(monkeypatch, client, app, profile_payload):
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
        assert_events(["OAUTH_PROFILE_INCOMPLETE", "OAUTH_LOGIN_SUCCESS"], ordered=True)
