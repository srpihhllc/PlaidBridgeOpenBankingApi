# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_oauth_routes.py

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
    keys = list(app.redis_client.store.keys())
    assert any("ttl:flow:oauth:google:failure" in k for k in keys)


def test_token_exchange_failure_traces_and_502(monkeypatch, client, app):
    # Force requests.post to raise
    def fake_post(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("requests.post", fake_post)
    resp = client.get("/callback/google?code=abc123")
    assert resp.status_code == 502

    keys = list(app.redis_client.store.keys())
    assert any("token_exchange:failure" in k for k in keys)


def test_token_exchange_success_without_access_token(monkeypatch, client, app):
    class DummyResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}  # no access_token

    monkeypatch.setattr("requests.post", lambda *a, **k: DummyResponse())
    resp = client.get("/callback/google?code=valid")
    assert resp.status_code == 401

    keys = list(app.redis_client.store.keys())
    assert any("token_exchange:failure" in k for k in keys)


def test_full_success_flow(monkeypatch, client, app):
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
            return {"email": "test@example.com"}

    monkeypatch.setattr("requests.get", lambda *a, **k: ProfileRes())

    resp = client.get("/callback/google?code=ok")
    # Should redirect to main.dashboard
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")

    keys = list(app.redis_client.store.keys())
    assert any("login:success" in k for k in keys)
    assert any("user:create" in k for k in keys)
