# =============================================================================
# FILE: app/tests/test_google_oauth.py
# DESCRIPTION: Tests for Google OAuth callback flows.
#              Inherits shared helpers from BaseOAuthTest.
# =============================================================================

import pytest
from flask import url_for
from requests.exceptions import HTTPError, Timeout

from .base_test_oauth import BaseOAuthTest


@pytest.mark.google
class TestGoogleOAuth(BaseOAuthTest):
    """Test suite for Google OAuth callbacks."""

    def test_google_success(self, monkeypatch, client, app):
        """Simulate a successful OAuth callback for Google."""

        def mock_post_token(url, data=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"access_token": "fake-google-token", "id_token": "fake-id"}

            return Resp()

        monkeypatch.setattr("requests.post", mock_post_token)

        def mock_get_profile(url, headers=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "email": "test@google.com",
                        "sub": "123",
                        "name": "Tester User",
                    }

            return Resp()

        monkeypatch.setattr("requests.get", mock_get_profile)

        resp = client.get(url_for("oauth.callback_google", code="abc123"))
        assert resp.status_code in (302, 303)
        self.assert_url_redirect(resp, "/dashboard")

        with app.app_context():
            self.assert_user_created(email="test@google.com")
            self.assert_events(
                ["OAUTH_LOGIN_SUCCESS", "SESSION_ESTABLISHED"],
                ordered=True,
            )

    @pytest.mark.parametrize(
        "mock_exception",
        [
            pytest.param(Timeout("Read timed out."), id="timeout"),
            pytest.param(
                HTTPError("500 Server Error: Internal Server Error"),
                id="http-error-500",
            ),
        ],
    )
    def test_google_token_failure_variants(self, monkeypatch, client, app, mock_exception):
        """Simulate different token exchange failure modes."""

        def mock_post(url, data=None, timeout=10):
            raise mock_exception

        monkeypatch.setattr("requests.post", mock_post)

        resp = client.get(url_for("oauth.callback_google", code="abc123"))
        assert resp.status_code == 502

        with app.app_context():
            self.assert_events(
                ["OAUTH_TOKEN_ERROR"],
                details={"OAUTH_TOKEN_ERROR": {"error": mock_exception.args[0]}},
            )
            self.assert_no_user()

    def test_google_profile_missing_email(self, monkeypatch, client, app):
        """Simulate Google profile response without email."""

        def mock_post(url, data=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"access_token": "fake-google-token"}

            return Resp()

        monkeypatch.setattr("requests.post", mock_post)

        def mock_get(url, headers=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"sub": "123", "name": "Tester User"}

            return Resp()

        monkeypatch.setattr("requests.get", mock_get)

        resp = client.get(url_for("oauth.callback_google", code="abc123"))
        assert resp.status_code == 401

        with app.app_context():
            self.assert_events(
                ["OAUTH_LOGIN_FAILURE"],
                details={"OAUTH_LOGIN_FAILURE": {"reason": "Profile payload missing email"}},
            )
            self.assert_no_user()

    @pytest.mark.parametrize(
        ("profile_payload", "missing_fields"),
        [
            pytest.param({"email": "test@google.com"}, ["sub", "name"], id="missing-sub-and-name"),
            pytest.param({"email": "test@google.com", "sub": "123"}, ["name"], id="missing-name"),
            pytest.param(
                {"email": "test@google.com", "name": "Tester User"},
                ["sub"],
                id="missing-sub",
            ),
        ],
    )
    def test_google_profile_incomplete_variants(
        self, monkeypatch, client, app, profile_payload, missing_fields
    ):
        """Simulate Google profile responses missing optional fields."""

        def mock_post(url, data=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"access_token": "fake-google-token", "id_token": "fake-id"}

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
        self.assert_url_redirect(resp, "/dashboard")

        with app.app_context():
            self.assert_user_created(email="test@google.com")
            self.assert_events(
                ["OAUTH_PROFILE_INCOMPLETE", "OAUTH_LOGIN_SUCCESS"],
                ordered=True,
                details={
                    "OAUTH_PROFILE_INCOMPLETE": {
                        "reason": f"Missing fields: {', '.join(missing_fields)}"
                    }
                },
            )
