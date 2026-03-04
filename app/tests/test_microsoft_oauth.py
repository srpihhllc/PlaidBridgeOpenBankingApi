# =============================================================================
# FILE: app/tests/test_microsoft_oauth.py
# DESCRIPTION: Tests for Microsoft OAuth callback flows.
#              Inherits shared helpers from BaseOAuthTest.
# =============================================================================

import pytest
from flask import url_for
from requests.exceptions import HTTPError, Timeout

from .base_test_oauth import BaseOAuthTest


@pytest.mark.microsoft
class TestMicrosoftOAuth(BaseOAuthTest):
    """Test suite for Microsoft OAuth callbacks."""

    def test_ms_success(self, monkeypatch, client, app):
        """Simulate a successful OAuth callback for Microsoft."""

        def mock_post_token(url, data=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "access_token": "fake-microsoft-token",
                        "id_token": "fake-id",
                    }

            return Resp()

        monkeypatch.setattr("requests.post", mock_post_token)

        def mock_get_profile(url, headers=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "mail": "test@microsoft.com",
                        "id": "456",
                        "displayName": "Tester User",
                    }

            return Resp()

        monkeypatch.setattr("requests.get", mock_get_profile)

        resp = client.get(url_for("oauth.callback_microsoft", code="def456"))
        assert resp.status_code in (302, 303)
        self.assert_url_redirect(resp, "/dashboard")

        with app.app_context():
            self.assert_user_created(email="test@microsoft.com")
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
    def test_ms_token_failure_variants(self, monkeypatch, client, app, mock_exception):
        """Simulate different token exchange failure modes."""

        def mock_post(url, data=None, timeout=10):
            raise mock_exception

        monkeypatch.setattr("requests.post", mock_post)

        resp = client.get(url_for("oauth.callback_microsoft", code="def456"))
        assert resp.status_code == 502

        with app.app_context():
            self.assert_events(
                ["OAUTH_TOKEN_ERROR"],
                details={"OAUTH_TOKEN_ERROR": {"error": mock_exception.args[0]}},
            )
            self.assert_no_user()

    def test_ms_profile_missing_email(self, monkeypatch, client, app):
        """Simulate Microsoft profile response without email."""

        def mock_post(url, data=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"access_token": "fake-microsoft-token"}

            return Resp()

        monkeypatch.setattr("requests.post", mock_post)

        def mock_get(url, headers=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"id": "456", "displayName": "Tester User"}

            return Resp()

        monkeypatch.setattr("requests.get", mock_get)

        resp = client.get(url_for("oauth.callback_microsoft", code="def456"))
        assert resp.status_code == 401

        with app.app_context():
            self.assert_events(
                ["OAUTH_LOGIN_FAILURE"],
                details={"OAUTH_LOGIN_FAILURE": {"reason": "Profile payload missing email"}},
            )
            self.assert_no_user()

    def test_ms_invalid_id_token(self, monkeypatch, client, app):
        """Simulate an invalid ID token during Microsoft OAuth callback."""

        def mock_post(url, data=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "access_token": "fake-microsoft-token",
                        "id_token": "bad-id-token",
                    }

            return Resp()

        monkeypatch.setattr("requests.post", mock_post)

        def mock_verify_token(token, *args, **kwargs):
            raise Exception("Invalid ID token")

        monkeypatch.setattr("app.services.oauth.verify_ms_token", mock_verify_token)

        def mock_get(url, headers=None, timeout=10):
            raise AssertionError("Profile endpoint should not be called when ID token is invalid")

        monkeypatch.setattr("requests.get", mock_get)

        resp = client.get(url_for("oauth.callback_microsoft", code="def456"))
        assert resp.status_code == 401

        with app.app_context():
            self.assert_events(
                ["OAUTH_IDTOKEN_INVALID"],
                details={"OAUTH_IDTOKEN_INVALID": {"reason": "ID token validation failed"}},
            )
            self.assert_no_user()
