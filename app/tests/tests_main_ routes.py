# =============================================================================
# FILE: app/tests/test_main_routes.py
# DESCRIPTION: Unit tests for app.routes.main endpoints.
# =============================================================================

import fnmatch
import json

import pytest

from app.routes.main import create_app

# ─── DummyRedis Stub ────────────────────────────────────────────────────────────


class DummyRedis:
    """
    In‑memory stand‑in for Redis.
    Supports setex, get, ttl, and globbing via keys().
    """

    def __init__(self):
        self.store = {}
        self.ttls = {}

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    def get(self, key):
        return self.store.get(key)

    def ttl(self, key):
        if key in self.store and key not in self.ttls:
            return -1
        return self.ttls.get(key, -2)

    def keys(self, pattern="*"):
        # Match keys directly as str, return as bytes
        return [key.encode() for key in self.store if fnmatch.fnmatch(key, pattern)]


# ─── FIXTURES ──────────────────────────────────────────────────────────────────


@pytest.fixture
def app(monkeypatch):
    """Provide a Flask app with DummyRedis and stubbed telemetry."""
    cfg = {"TESTING": True, "SECRET_KEY": "test-secret"}
    app = create_app(cfg)

    dummy = DummyRedis()
    monkeypatch.setattr(app, "redis_client", dummy)

    # Stub out telemetry emitter
    monkeypatch.setattr("app.routes.main.emit_narrative_trace", lambda *a, **k: None)

    return app


@pytest.fixture
def client(app):
    """Provide a test client for the Flask app."""
    return app.test_client()


# ─── TESTS ─────────────────────────────────────────────────────────────────────


def test_main_home_route_renders_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"FinBrain" in resp.data


def test_main_dispute_form(client):
    resp = client.get("/dispute-form")
    assert resp.status_code == 200
    assert b"<form" in resp.data


@pytest.mark.parametrize(
    ("payload", "content_type", "expected_status", "expected_snip"),
    [
        ("not-json", "text/plain", 400, b"Request must be JSON"),
        (
            json.dumps({"foo": "bar"}),
            "application/json",
            400,
            b"Missing required fields",
        ),
    ],
)
def test_main_process_transaction_api_errors(
    client, payload, content_type, expected_status, expected_snip
):
    resp = client.post("/api/transactions", data=payload, content_type=content_type)
    assert resp.status_code == expected_status
    assert expected_snip in resp.data


def test_main_process_transaction_api_success(client):
    valid = {"amount": "12.34", "description": "test", "account_id": "A1"}
    resp = client.post(
        "/api/transactions",
        data=json.dumps(valid),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["transaction_id"].startswith("MOCK_")


def test_main_login_required_redirects(client):
    # Unauthenticated request to a protected route
    r1 = client.get("/welcome_back")
    assert r1.status_code == 302
    assert "/login" in r1.headers["Location"]

    r2 = client.post("/api/transactions", json={})
    assert r2.status_code == 302
    assert "/login" in r2.headers["Location"]


def test_main_blueprint_inspector_tile(client, app, monkeypatch):
    # Stub out the inspect_blueprints call inside the tile
    fake = {"main": {"status": "registered", "routes": []}}
    monkeypatch.setattr(
        "app.cockpit.tiles.blueprint_inspector.inspect_blueprints",
        lambda: fake,
    )

    resp = client.get("/cockpit/blueprint_inspector")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert isinstance(data["payload"], dict)
    assert data["payload"] == fake
