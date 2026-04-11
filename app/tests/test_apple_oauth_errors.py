# =============================================================================
# FILE: app/tests/test_apple_oauth_errors.py
# DESCRIPTION: Tests Apple error paths: token exchange failure and profile fetch failure.
# =============================================================================

import json
import pytest
from flask import url_for

from app.oauth.provider import ProviderName


def test_apple_token_exchange_failure(monkeypatch, client, app):
    # Make provider.exchange_code raise (simulate requests.post Timeout)
    def mock_exchange(self, code):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr("app.oauth.provider.OAuthProvider.exchange_code", mock_exchange)

    # Ensure tests use POST form for Apple
    resp = client.post("/oauth/callback/apple", data={"code": "abc123"})
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
    # exchange_code returns token data but fetch_profile raises
    def mock_exchange(self, code):
        return {"id_token": "fake", "access_token": "fake"}

    def mock_fetch(self, token_data):
        raise RuntimeError("profile service down")

    monkeypatch.setattr("app.oauth.provider.OAuthProvider.exchange_code", mock_exchange)
    monkeypatch.setattr("app.oauth.provider.OAuthProvider.fetch_profile", mock_fetch)

    resp = client.post("/oauth/callback/apple", data={"code": "abc123"})
    assert resp.status_code == 502

    with app.app_context():
        from app.models import TraceEvent

        events = TraceEvent.query.all()
        types = [e.event_type for e in events]
        assert types == ["OAUTH_PROFILE_ERROR"]
        meta = json.loads(events[0].meta)
        assert "profile service down" in meta["error"]