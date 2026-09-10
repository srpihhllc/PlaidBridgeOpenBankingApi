# =============================================================================
# FILE: app/tests/test_webhooks_routes.py
# DESCRIPTION: Smoke + contract tests for the webhooks blueprint.
# =============================================================================

import hashlib
import hmac
import json
import uuid

import pytest
import sqlalchemy as sa

from app import create_app, db
from app.models.borrower_card import BorrowerCard
from app.models.user import User
from app.models.vault_transaction import VaultTransaction

TEST_ACH_SECRET = "test_ach_webhook_secret_key_12345"
TEST_PLAID_SECRET = "test_plaid_webhook_secret_key_12345"


@pytest.fixture
def app():
    application = create_app("app.config.TestConfig")
    application.config["ACH_WEBHOOK_SECRET"] = TEST_ACH_SECRET
    application.config["PLAID_WEBHOOK_SECRET"] = TEST_PLAID_SECRET
    application.config["DEBUG"] = True

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
    """Helper to create a valid borrower and card with explicit UUID keys."""
    user_uuid = str(uuid.uuid4())
    user = User(
        id=user_uuid,
        email="borrower@example.com",
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


def _compute_hmac_signature(secret: str, raw_bytes: bytes) -> str:
    return hmac.new(
        secret.encode("utf-8"), raw_bytes, hashlib.sha256
    ).hexdigest()


# -------------------------------------------------------------------------
# ACH webhook tests
# -------------------------------------------------------------------------
def test_ach_listener_creates_txn_success(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": 50.0}
    raw_body = json.dumps(payload).encode("utf-8")

    headers = {
        "X-ACH-Signature": _compute_hmac_signature(TEST_ACH_SECRET, raw_body),
        "Content-Type": "application/json",
    }

    # UPDATED: Target the route directly mapped under the blueprint registration prefix
    resp = client.post("/webhooks/ach", data=raw_body, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert "recorded" in data["detail"] or "synced" in data["detail"]

    with app.app_context():
        txns = VaultTransaction.query.all()
        assert len(txns) == 1
        assert txns[0].method == "ACH"
        assert float(txns[0].amount) == 50.0
        assert str(txns[0].borrower_id) == str(user_id)
        assert txns[0].card_id == card_id


def test_ach_listener_rejects_missing_fields(client):
    payload = {"borrower_id": "missing_card_and_amount"}
    raw_body = json.dumps(payload).encode("utf-8")

    headers = {
        "X-ACH-Signature": _compute_hmac_signature(TEST_ACH_SECRET, raw_body),
        "Content-Type": "application/json",
    }

    resp = client.post("/webhooks/ach", data=raw_body, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()

    assert data["status"] == "error"
    assert data["code"] == "E_WEBHOOK_INVALID_PAYLOAD"


def test_ach_listener_rejects_invalid_signature(client):
    payload = {"borrower_id": "1", "card_id": 1, "amount": 50.0}
    headers = {
        "X-ACH-Signature": "invalid_signature_hash",
        "Content-Type": "application/json",
    }

    resp = client.post("/webhooks/ach", json=payload, headers=headers)
    assert resp.status_code == 401
    assert resp.get_json()["code"] == "E_WEBHOOK_ACH_INVALID_SIGNATURE"


# -------------------------------------------------------------------------
# Plaid webhook tests
# -------------------------------------------------------------------------
def test_plaid_listener_creates_txn_success(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": "75.0"}
    raw_body = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Plaid-Signature": _compute_hmac_signature(
            TEST_PLAID_SECRET, raw_body
        ),
        "Content-Type": "application/json",
    }

    resp = client.post("/webhooks/plaid", data=raw_body, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert "recorded" in data["detail"] or "synced" in data["detail"]


def test_plaid_listener_rejects_invalid_amount(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": -10}
    raw_body = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Plaid-Signature": _compute_hmac_signature(
            TEST_PLAID_SECRET, raw_body
        ),
        "Content-Type": "application/json",
    }

    resp = client.post("/webhooks/plaid", data=raw_body, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "E_WEBHOOK_INVALID_PAYLOAD"


# -------------------------------------------------------------------------
# Reconcile webhook tests
# -------------------------------------------------------------------------
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

    payload = {
        "txn_id": txn_id,
        "borrower_id": user_id,
        "card_id": card_id,
    }
    resp = client.post("/webhooks/reconcile", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert "complete" in data["detail"] or "reconciled" in data["detail"]


def test_reconcile_returns_not_found_for_missing_txn(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {
        "txn_id": 999999,
        "borrower_id": user_id,
        "card_id": card_id,
    }
    resp = client.post("/webhooks/reconcile", json=payload)
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "E_WEBHOOK_RECONCILE_NOT_FOUND"


def test_webhook_cross_tenant_violation_rejection(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()
        rogue_user = User(
            id=str(uuid.uuid4()),
            email="attacker@example.com",
            password_hash="malicious",
        )
        db.session.add(rogue_user)
        db.session.commit()
        rogue_id = rogue_user.id

    payload = {"borrower_id": rogue_id, "card_id": card_id, "amount": 50.0}
    raw_body = json.dumps(payload).encode("utf-8")

    headers = {
        "X-ACH-Signature": _compute_hmac_signature(TEST_ACH_SECRET, raw_body),
        "Content-Type": "application/json",
    }

    resp = client.post("/webhooks/ach", data=raw_body, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "E_WEBHOOK_TENANT_VIOLATION"
