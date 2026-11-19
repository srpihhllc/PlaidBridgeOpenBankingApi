# =============================================================================
# FILE: app/tests/test_webhooks_routes.py
# DESCRIPTION: Smoke + contract tests for the webhooks blueprint.
# =============================================================================

# app/tests/test_webhooks_routes.py
import base64
import hashlib
import hmac
import json
import time
import uuid

import jwt
import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric import ec

from app import create_app, db
from app.models.borrower_card import BorrowerCard
from app.models.user import User
from app.models.vault_transaction import VaultTransaction

TEST_ACH_SECRET = "test_ach_webhook_secret_key_12345"
TEST_RECONCILE_SECRET = "test_reconcile_webhook_secret_key_12345"


@pytest.fixture
def app():
    application = create_app("app.config.TestConfig")
    application.config.update(
        ACH_WEBHOOK_SECRET=TEST_ACH_SECRET,
        RECONCILE_WEBHOOK_SECRET=TEST_RECONCILE_SECRET,
        PLAID_CLIENT_ID="test-plaid-client",
        PLAID_SECRET="test-plaid-secret",
        PLAID_API_BASE_URL="https://sandbox.plaid.com",
    )

    with application.app_context():
        db.create_all()
        yield application
        try:
            db.session.remove()
            dialect = db.engine.dialect.name.lower()
            if dialect == "mysql":
                with db.engine.connect() as conn:
                    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
                    conn.commit()
            db.drop_all()
            if dialect == "mysql":
                with db.engine.connect() as conn:
                    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))
                    conn.commit()
        except Exception:
            pass


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_user_and_card():
    user = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test",
    )
    db.session.add(user)
    db.session.flush()

    card = BorrowerCard(
        user_id=user.id,
        card_number="1234567890123456",
        expiration_date="12/30",
        cvv="123",
        score=700,
        color="black",
    )
    db.session.add(card)
    db.session.commit()
    return str(user.id), int(card.id)


def _hmac_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _b64url(value: int) -> str:
    return base64.urlsafe_b64encode(value.to_bytes(32, "big")).rstrip(b"=").decode()


def _plaid_headers(body: bytes, monkeypatch):
    """Create a real ES256 test JWT and mock Plaid's verification-key response."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    key_id = "test-key-id"

    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(public_numbers.x),
        "y": _b64url(public_numbers.y),
        "alg": "ES256",
        "kid": key_id,
        "use": "sig",
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"key": jwk}

    def fake_post(url, *, headers, json, timeout):
        assert url.endswith("/webhook_verification_key/get")
        assert json == {"key_id": key_id}
        return FakeResponse()

    monkeypatch.setattr("app.webhooks.views.requests.post", fake_post)

    token = jwt.encode(
        {
            "iat": int(time.time()),
            "request_body_sha256": hashlib.sha256(body).hexdigest(),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )
    return {"Plaid-Verification": token, "Content-Type": "application/json"}


def test_ach_listener_creates_txn_success(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": 50.0}
    body = json.dumps(payload).encode()
    response = client.post(
        "/webhooks/ach",
        data=body,
        headers={
            "X-ACH-Signature": _hmac_signature(TEST_ACH_SECRET, body),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["detail"] == "recorded"

    with app.app_context():
        txn = VaultTransaction.query.one()
        assert txn.method == "ACH"
        assert float(txn.amount) == 50.0
        assert str(txn.borrower_id) == user_id
        assert txn.card_id == card_id


def test_ach_listener_rejects_missing_fields(client):
    body = json.dumps({"borrower_id": "missing-fields"}).encode()
    response = client.post(
        "/webhooks/ach",
        data=body,
        headers={
            "X-ACH-Signature": _hmac_signature(TEST_ACH_SECRET, body),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "E_WEBHOOK_INVALID_PAYLOAD"


def test_ach_listener_rejects_invalid_signature(client):
    response = client.post(
        "/webhooks/ach",
        json={"borrower_id": "1", "card_id": 1, "amount": 50.0},
        headers={"X-ACH-Signature": "invalid"},
    )
    assert response.status_code == 401
    assert response.get_json()["code"] == "E_WEBHOOK_ACH_INVALID_SIGNATURE"


def test_plaid_listener_verifies_and_dispatches_event(client, app, monkeypatch):
    payload = {
        "webhook_type": "TRANSACTIONS",
        "webhook_code": "SYNC_UPDATES_AVAILABLE",
        "item_id": "test-item",
    }
    body = json.dumps(payload).encode()
    received = []
    app.extensions["plaid_webhook_handler"] = received.append

    response = client.post(
        "/webhooks/plaid",
        data=body,
        headers=_plaid_headers(body, monkeypatch),
    )

    assert response.status_code == 200
    assert response.get_json()["detail"] == "accepted"
    assert received == [payload]


def test_plaid_listener_rejects_tampered_body(client, app, monkeypatch):
    signed_body = json.dumps({"webhook_type": "TRANSACTIONS"}).encode()
    headers = _plaid_headers(signed_body, monkeypatch)

    response = client.post(
        "/webhooks/plaid",
        data=json.dumps({"webhook_type": "ITEM"}).encode(),
        headers=headers,
    )
    assert response.status_code == 401


def test_plaid_listener_returns_503_without_handler(client, app, monkeypatch):
    payload = {"webhook_type": "TRANSACTIONS", "item_id": "test-item"}
    body = json.dumps(payload).encode()
    app.extensions.pop("plaid_webhook_handler", None)

    response = client.post(
        "/webhooks/plaid",
        data=body,
        headers=_plaid_headers(body, monkeypatch),
    )
    assert response.status_code == 503
    assert response.get_json()["code"] == "E_WEBHOOK_HANDLER_UNAVAILABLE"


def test_reconcile_updates_txn_success(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()
        txn = VaultTransaction(
            borrower_id=user_id,
            card_id=card_id,
            amount=100.0,
            method="ACH",
            reconciled=False,
        )
        db.session.add(txn)
        db.session.commit()
        txn_id = txn.id

    payload = {"txn_id": txn_id, "borrower_id": user_id}
    body = json.dumps(payload).encode()
    response = client.post(
        "/webhooks/reconcile",
        data=body,
        headers={
            "X-Reconcile-Signature": _hmac_signature(TEST_RECONCILE_SECRET, body),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["detail"] == "complete"


def test_reconcile_returns_not_found_for_missing_txn(client, app):
    with app.app_context():
        user_id, _ = _seed_user_and_card()

    payload = {"txn_id": 999999, "borrower_id": user_id}
    body = json.dumps(payload).encode()
    response = client.post(
        "/webhooks/reconcile",
        data=body,
        headers={
            "X-Reconcile-Signature": _hmac_signature(TEST_RECONCILE_SECRET, body),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "E_WEBHOOK_RECONCILE_NOT_FOUND"

