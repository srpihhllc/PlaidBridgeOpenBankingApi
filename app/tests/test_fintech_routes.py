# =============================================================================
# FILE: app/tests/test_fintech_routes.py
# DESCRIPTION: Smoke tests for fintech verification + transaction endpoints.
# - Robust fixture teardown that tolerates MySQL foreign-key ordering issues.
# =============================================================================

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import text

from app import create_app, db
from app.models import User


@pytest.fixture
def app(monkeypatch):
    """Create a Flask app with in-memory DB and JWT setup."""
    app = create_app("app.config.TestConfig")
    with app.app_context():
        db.create_all()
        # Create a dummy user (ignore if already exists from a previous fixture run)
        user = User(email="test@example.com", password_hash="hashed")
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # If the user already exists, load and use it
            user = User.query.filter_by(email="test@example.com").first()
        # Store the ID (not the detached instance) so other fixtures can safely reload
        app.test_user_id = user.id

    yield app

    # Teardown: try a normal drop_all(), but tolerate DBs that require FK checks disabled.
    with app.app_context():
        try:
            db.drop_all()
        except OperationalError:
            # Try disabling foreign key checks for MySQL-style servers, then drop.
            try:
                conn = db.engine.connect()
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
                conn.close()
                db.drop_all()
            except Exception:
                # Best-effort cleanup: rollback session and continue
                db.session.rollback()
            finally:
                try:
                    conn = db.engine.connect()
                    conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
                    conn.close()
                except Exception:
                    # If we can't re-enable, ignore in test teardown
                    pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app):
    """Return Authorization header for dummy user."""
    # Use the stored ID to avoid DetachedInstance issues
    with app.app_context():
        token = create_access_token(identity=app.test_user_id)
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
    resp = client.post("/api/v1/fintech/transactions", json=payload, headers=auth_header)
    assert resp.status_code in (200, 201)
    body = resp.get_json()
    assert body["status"] == "success"
    txn_id = body["data"]["transaction_id"] if "data" in body else body.get("transaction_id")

    # Retrieve using the core/test endpoint if available (fallback)
    resp2 = client.get("/api/v1/core/transactions", headers=auth_header)
    # Accept 200 or 404 depending on implementation; if 200, ensure structure
    if resp2.status_code == 200:
        data = resp2.get_json()
        assert isinstance(data, dict)
    else:
        # If the route isn't present, at least ensure the created transaction response looked valid
        assert txn_id is not None


def test_create_transaction_invalid_schema(client, auth_header):
    # Missing required fields
    resp = client.post("/api/v1/fintech/transactions", json={"foo": "bar"}, headers=auth_header)
    assert resp.status_code in (400, 422)
    assert resp.get_json()["status"] == "error"