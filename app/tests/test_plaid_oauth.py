# =============================================================================
# FILE: app/tests/test_plaid_oauth.py
# DESCRIPTION: Tests for Plaid OAuth callback flows.
#              Inherits shared helpers from BaseOAuthTest.
# =============================================================================

import pytest
from flask import url_for
from requests.exceptions import HTTPError, Timeout

from .base_test_oauth import BaseOAuthTest


@pytest.mark.plaid
class TestPlaidOAuth(BaseOAuthTest):
    """Test suite for Plaid OAuth callbacks."""

    def test_plaid_success(self, monkeypatch, client, app):
        """Simulate a successful Plaid OAuth public_token exchange."""
        access_token_mock = "access-token-xyz"
        item_id_mock = "item-id-123"

        def mock_exchange(url, json=None, timeout=10):
            assert url.endswith("/item/public_token/exchange")
            assert json.get("public_token") == "public-token-abc"

            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"access_token": access_token_mock, "item_id": item_id_mock}

            return Resp()

        monkeypatch.setattr("requests.post", mock_exchange)

        mock_user = self.setup_mock_user()

        resp = client.get(
            url_for(
                "oauth.callback_plaid",
                public_token="public-token-abc",
                user_id=mock_user.id,
            )
        )
        assert resp.status_code in (302, 303)
        self.assert_url_redirect(resp, "/dashboard")

        with app.app_context():
            self.assert_plaid_item_created(
                user_id=mock_user.id,
                item_id=item_id_mock,
                access_token=access_token_mock,
            )
            self.assert_events(
                ["PLAID_ACCESS_TOKEN_EXCHANGE_SUCCESS", "SESSION_ESTABLISHED"],
                ordered=True,
            )

    @pytest.mark.parametrize(
        "mock_exception",
        [
            pytest.param(Timeout("Read timed out."), id="timeout"),
            pytest.param(HTTPError("400 Bad Request: INVALID_PUBLIC_TOKEN"), id="invalid-token"),
        ],
    )
    def test_plaid_exchange_failure_variants(self, monkeypatch, client, app, mock_exception):
        """Simulate different public_token exchange failure modes."""

        def mock_exchange(url, json=None, timeout=10):
            raise mock_exception

        monkeypatch.setattr("requests.post", mock_exchange)

        resp = client.get(url_for("oauth.callback_plaid", public_token="bad-public-token"))
        assert resp.status_code == 502

        with app.app_context():
            events = self.assert_events(["PLAID_ACCESS_TOKEN_EXCHANGE_FAILURE"])
            self.assert_no_user()
            assert mock_exception.args[0] in events[0].details.get("error")

    def test_plaid_missing_public_token(self, client, app):
        """Simulate callback with no public_token provided."""
        resp = client.get(url_for("oauth.callback_plaid"))
        assert resp.status_code == 400

        with app.app_context():
            self.assert_events(
                ["PLAID_PUBLIC_TOKEN_MISSING"],
                details={"PLAID_PUBLIC_TOKEN_MISSING": {"reason": "Missing public_token"}},
            )
            self.assert_no_user()

    def test_plaid_exchange_returns_no_access_token(self, monkeypatch, client, app):
        """Simulate Plaid exchange response missing access_token."""

        def mock_exchange(url, json=None, timeout=10):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"item_id": "item-id-123"}  # no access_token

            return Resp()

        monkeypatch.setattr("requests.post", mock_exchange)

        resp = client.get(url_for("oauth.callback_plaid", public_token="public-token-abc"))
        assert resp.status_code == 401

        with app.app_context():
            self.assert_events(
                ["PLAID_ACCESS_TOKEN_EXCHANGE_FAILURE"],
                details={"PLAID_ACCESS_TOKEN_EXCHANGE_FAILURE": {"reason": "No access_token"}},
            )
            self.assert_no_user()
