# tests/test_oauth_routes.py

import pytest

from app import create_app


# -- Fake Redis Client --------------------------------------------------------
class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ttls = {}

    def setex(self, key, ttl, value):
        # record value and timestamp
        self.store[key] = value
        self.ttls[key] = ttl

    def ttl(self, key):
        return self.ttls.get(key, -2)

    def get(self, key):
        return self.store.get(key)


# -- Helper -----------------------------------------------------------------
def _get_string_keys(app) -> list[str]:
    """Helper to extract and decode Redis keys regardless of byte/str format."""
    raw_keys = list(app.redis_client.store.keys())
    return [
        k.decode("utf-8") if isinstance(k, bytes) else str(k) for k in raw_keys
    ]


# -- Fixtures ---------------------------------------------------------------
@pytest.fixture
def app():
    # Use your testing config that doesn’t require real Redis
    app = create_app(config_class="TestingConfig")
    # Swap in fake Redis
    app.redis_client = FakeRedis()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# -- Tests ------------------------------------------------------------------
def test_missing_code_returns_400_and_ttl_emit(client, app):
    resp = client.get("/callback/google")
    assert resp.status_code == 400

    # The FakeRedis.store should have a missing-code key
    keys = _get_string_keys(app)
    assert any("ttl:flow:oauth:google:failure" in k for k in keys)


def test_token_exchange_failure_traces_and_502(monkeypatch, client, app):
    # Seed session state to pass CSRF validation
    test_state = "test-google-state-502"
    with client.session_transaction() as sess:
        sess["oauth_state:google"] = test_state

    # Force requests.post to raise
    def fake_post(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("requests.post", fake_post)
    resp = client.get(f"/callback/google?code=abc123&state={test_state}")
    assert resp.status_code == 502

    keys = _get_string_keys(app)
    assert any("ttl:flow:oauth:google:failure" in k for k in keys)


def test_token_exchange_success_without_access_token(monkeypatch, client, app):
    # Seed session state to pass CSRF validation
    test_state = "test-google-state-empty"
    with client.session_transaction() as sess:
        sess["oauth_state:google"] = test_state

    class DummyTokenResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}  # missing access_token

    class DummyProfileResponse:
        def raise_for_status(self):
            from requests.exceptions import HTTPError

            raise HTTPError("401 Client Error: Unauthorized", response=self)

        def json(self):
            return {"error": "unauthorized"}

    # Mock token request (returns empty payload)
    monkeypatch.setattr("requests.post", lambda *a, **k: DummyTokenResponse())

    # Mock profile request (prevents unhandled network call out to Google)
    monkeypatch.setattr("requests.get", lambda *a, **k: DummyProfileResponse())

    resp = client.get(f"/callback/google?code=valid&state={test_state}")
    assert resp.status_code == 502

    keys = _get_string_keys(app)
    assert any("ttl:flow:oauth:google:failure" in k for k in keys)


def test_full_success_flow(monkeypatch, client, app):
    # Seed session state to pass CSRF validation
    test_state = "test-google-state-success"
    with client.session_transaction() as sess:
        sess["oauth_state:google"] = test_state

    # Stub token exchange
    class TokenRes:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "tok", "id_token": "id"}

    monkeypatch.setattr("requests.post", lambda *a, **k: TokenRes())

    # Stub profile fetch
    class ProfileRes:
        def raise_for_status(self):
            pass

        def json(self):
            return {"email": "test@example.com", "sub": "12345"}

    monkeypatch.setattr("requests.get", lambda *a, **k: ProfileRes())

    resp = client.get(f"/callback/google?code=ok&state={test_state}")
    # Should redirect to main.dashboard
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")

    keys = _get_string_keys(app)
    assert any(
        "login:success" in k or "oauth:google:success" in k or "user" in k
        for k in keys
    )
