# =============================================================================
# FILE: app/tests/test_oauth_multi_provider.py
# DESCRIPTION: Test harness for multi-provider OAuth callback flows.
# =============================================================================

import pytest
from flask import url_for

from app.oauth.provider import ProviderName


@pytest.mark.parametrize("provider", [ProviderName.GOOGLE, ProviderName.MICROSOFT, ProviderName.APPLE])
def test_oauth_callback_multi_provider(monkeypatch, client, app, provider):
    """
    End-to-end unit test for the unified /oauth/callback/<provider> route.

    This test monkeypatches the provider.exchange_code and provider.fetch_profile
    to produce deterministic token and profile payloads for each provider.
    """
    # Deterministic token response and profile per provider
    token_response = {"access_token": f"fake-{provider.value}-access", "id_token": f"fake-{provider.value}-id"}
    profile_response = {"email": f"test+{provider.value}@example.com", "sub": "123", "name": "Tester"}

    # Monkeypatch the OAuthProvider methods used by the route
    from app.oauth import provider as provider_module

    def mock_exchange(self, code):
        assert code == "abc123"
        return token_response

    def mock_fetch_profile(self, token_data):
        # ensure we receive token_data dict in tests
        assert isinstance(token_data, dict)
        return profile_response

    monkeypatch.setattr(provider_module.OAuthProvider, "exchange_code", mock_exchange)
    monkeypatch.setattr(provider_module.OAuthProvider, "fetch_profile", mock_fetch_profile)

    # Build the URL for the unified route
    resp = client.get(url_for("oauth.callback_provider", provider=provider.value, code="abc123"))
    # Expect redirect to dashboard
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/dashboard")

    # Verify user created and events inserted
    with app.app_context():
        from app.models import User, TraceEvent

        u = User.query.filter_by(email=profile_response["email"]).first()
        assert u is not None

        # Two ordered trace events should exist (OAUTH_LOGIN_SUCCESS, SESSION_ESTABLISHED)
        events = TraceEvent.query.order_by(TraceEvent.id).all()
        types = [e.event_type for e in events if e.user_id == u.id]
        assert types[:2] == ["OAUTH_LOGIN_SUCCESS", "SESSION_ESTABLISHED"]