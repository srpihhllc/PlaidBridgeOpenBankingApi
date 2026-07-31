# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_pkce_state.py

import re
from app.oauth.provider import ProviderName


def test_pkce_and_state_are_set_on_login(client, app):
    # Initiate login for Google (login initiates PKCE + state)
    resp = client.get(f"/login/{ProviderName.GOOGLE.value}")
    assert resp.status_code in (302, 303)
    loc = resp.headers["Location"]
    # code_challenge and state should be present in redirect URL
    assert "code_challenge=" in loc
    assert "state=" in loc

    # Basic smoke: ensure state validation accepts the same state
    # Start a client session and extract state
    with client:
        resp2 = client.get(f"/login/{ProviderName.GOOGLE.value}")
        assert resp2.status_code in (302, 303)
        m = re.search(r"state=([^&]+)", resp2.headers["Location"])
        assert m
        state = m.group(1)
        cb = client.get(f"/callback/{ProviderName.GOOGLE.value}?code=abc123&state={state}")
        assert cb.status_code != 400


def test_state_mismatch_returns_400(client, app):
    # Start login (so a state is stored)
    resp = client.get(f"/login/{ProviderName.GOOGLE.value}")
    assert resp.status_code in (302, 303)
    # Call callback with wrong state
    resp2 = client.get(f"/callback/{ProviderName.GOOGLE.value}?code=abc123&state=invalid-state")
    assert resp2.status_code == 400