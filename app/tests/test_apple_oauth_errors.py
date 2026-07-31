# =============================================================================
# FILE: app/tests/test_apple_oauth_errors.py
# DESCRIPTION: Tests Apple error paths: token exchange failure and profile fetch failure.
# =============================================================================

import json
import requests
from flask import url_for

from app.oauth.provider import ProviderName


def test_apple_token_exchange_failure(monkeypatch, client, app):
    # Raise a requests Timeout exception to trigger the OAUTH_TOKEN_ERROR trace event path
    def mock_exchange(self, code):
        raise requests.exceptions.Timeout("simulated timeout")

    monkeypatch.setattr("app.oauth.provider.OAuthProvider.exchange_code", mock_exchange)

    # Set expected state in test session for CSRF check
    test_state = "test-state-apple"
    with client.session_transaction() as sess:
        sess["oauth_state:apple"] = test_state

    # POST form with code and matching state
    resp = client.post(
        url_for("oauth.callback_provider", provider=ProviderName.APPLE.value), 
        data={
            "code": "abc123",
            "state": test_state,
        }
    )
    assert resp.status_code == 502

    with app.app_context():
        from app.models import TraceEvent

        events = TraceEvent.query.all()
        # Only one event and it's OAUTH_TOKEN_ERROR
        types = [e.event_type for e in events]
        assert types == ["OAUTH_TOKEN_ERROR"]
        meta = json.loads(events[0].meta)
        assert meta["error"].startswith("simulated timeout")


def test_apple_profile_fetch_failure(monkeypatch, client, app):
    # exchange_code returns token data but fetch_profile raises a requests HTTPError
    def mock_exchange(self, code):
        return {"id_token": "fake", "access_token": "fake"}

    def mock_fetch(self, token_data):
        raise requests.exceptions.HTTPError("profile service down")

    monkeypatch.setattr("app.oauth.provider.OAuthProvider.exchange_code", mock_exchange)
    monkeypatch.setattr("app.oauth.provider.OAuthProvider.fetch_profile", mock_fetch)

    # Set expected state in test session for CSRF check
    test_state = "test-state-apple"
    with client.session_transaction() as sess:
        sess["oauth_state:apple"] = test_state

    # POST form with code and matching state
    resp = client.post(
        url_for("oauth.callback_provider", provider=ProviderName.APPLE.value), 
        data={
            "code": "abc123",
            "state": test_state,
        }
    )
    assert resp.status_code == 502

    with app.app_context():
        from app.models import TraceEvent

        events = TraceEvent.query.all()
        types = [e.event_type for e in events]
        assert types == ["OAUTH_PROFILE_ERROR"]
        meta = json.loads(events[0].meta)
        assert "profile service down" in meta["error"]