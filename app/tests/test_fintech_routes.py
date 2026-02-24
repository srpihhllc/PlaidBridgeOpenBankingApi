# =============================================================================
# FILE: app/tests/test_fintech_routes.py
# DESCRIPTION: Smoke tests for fintech verification + transaction endpoints.
# =============================================================================

import pytest
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models import User


@pytest.fixture
def app(monkeypatch):
    """Create a Flask app with in-memory DB and JWT setup."""
    app = create_app("app.config.TestConfig")
    with app.app_context():
        db.create_all()
        # Create a dummy user
        user = User(email="test@example.com", password_hash="hashed")
        db.session.add(user)
        db.session.commit()
        app.test_user = user
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app):
    """Return Authorization header for dummy user."""
    with app.app_context():
        token = create_access_token(identity=app.test_user.id)
    return {"Authorization": f"Bearer {token}"}


# --- Verification Endpoints ---------------------------------------------------


def test_health_endpoint(client):
    resp = client.get("/api/v1/fintech/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert any("fintech" in r for r in data["routes"])


def test_verify_truelayer_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.fintech_api.verify_via_truelayer",
        lambda payload: {"verified": True},
    )
    resp = client.post("/api/v1/fintech/verify/truelayer", json={"foo": "bar"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"


def test_verify_truelayer_error(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.fintech_api.verify_via_truelayer",
        lambda payload: {"error": "bad token"},
    )
    resp = client.post("/api/v1/fintech/verify/truelayer", json={"foo": "bar"})
    assert resp.status_code == 400
    assert resp.get_json()["status"] == "error"


def test_verify_tink_success(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.fintech_api.verify_via_tink", lambda payload: {"verified": True}
    )
    resp = client.post("/api/v1/fintech/verify/tink", json={"foo": "bar"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"


# --- Transaction Endpoints ----------------------------------------------------


def test_create_transaction_and_get(client, app, auth_header):
    payload = {
        "amount": 123.45,
        "date": "2025-01-01T12:00:00",
        "name": "Test Transaction",
        "category": "TestCat",
    }
    # Create
    resp = client.post("/api/v1/transactions", json=payload, headers=auth_header)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "success"
    txn_id = body["transaction_id"]

    # Retrieve
    resp2 = client.get("/api/v1/transactions", headers=auth_header)
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data["count"] == 1
    assert data["data"][0]["id"] == txn_id


def test_create_transaction_invalid_schema(client, auth_header):
    # Missing required fields
    resp = client.post("/api/v1/transactions", json={"foo": "bar"}, headers=auth_header)
    assert resp.status_code in (400, 422)
    assert resp.get_json()["status"] == "error"
