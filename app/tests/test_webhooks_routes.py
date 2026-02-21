# =============================================================================
# FILE: app/tests/test_webhooks_routes.py
# DESCRIPTION: Smoke + contract tests for the webhooks blueprint.
# Verifies ACH, Plaid, and Reconcile endpoints:
#   - register correctly
#   - enforce payload validation
#   - respect VaultTransaction safety
#   - return structured JSON with status/code/message
# =============================================================================


import pytest

from app import create_app, db
from app.models.borrower_card import BorrowerCard
from app.models.user import User
from app.models.vault_transaction import VaultTransaction


@pytest.fixture
def app():
    app = create_app("app.config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_user_and_card():
    """Helper to create a valid borrower and card."""
    user = User(
        email="borrower@example.com",
        password_hash="test",
    )
    db.session.add(user)
    db.session.commit()

    card = BorrowerCard(
        user_id=user.id,
        card_number_last4="1234",
        status="active",
    )
    db.session.add(card)
    db.session.commit()

    return user, card


# -------------------------------------------------------------------------
# ACH webhook tests
# -------------------------------------------------------------------------
def test_ach_listener_creates_txn_success(client, app):
    with app.app_context():
        user, card = _seed_user_and_card()

    payload = {"borrower_id": user.id, "card_id": card.id, "amount": 50.0}
    resp = client.post("/webhooks/ach", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert data["detail"] == "ACH transaction recorded"

    with app.app_context():
        txns = VaultTransaction.query.all()
        assert len(txns) == 1
        assert txns[0].method == "ACH"
        assert float(txns[0].amount) == 50.0
        assert txns[0].borrower_id == user.id
        assert txns[0].card_id == card.id


def test_ach_listener_rejects_missing_fields(client):
    payload = {"borrower_id": "missing_card_and_amount"}
    resp = client.post("/webhooks/ach", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()

    assert data["status"] == "error"
    assert data["code"] == "E_WEBHOOK_INVALID_PAYLOAD"
    assert "missing_fields" in data.get("extra", {})


# -------------------------------------------------------------------------
# Plaid webhook tests
# -------------------------------------------------------------------------
def test_plaid_listener_creates_txn_success(client, app):
    with app.app_context():
        user, card = _seed_user_and_card()

    payload = {"borrower_id": user.id, "card_id": card.id, "amount": "75.0"}
    resp = client.post("/webhooks/plaid", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert data["detail"] == "Plaid transaction recorded"

    with app.app_context():
        txns = VaultTransaction.query.all()
        assert len(txns) == 1
        assert txns[0].method == "Plaid"
        assert float(txns[0].amount) == 75.0
        assert txns[0].borrower_id == user.id
        assert txns[0].card_id == card.id


def test_plaid_listener_rejects_invalid_amount(client, app):
    with app.app_context():
        user, card = _seed_user_and_card()

    payload = {"borrower_id": user.id, "card_id": card.id, "amount": -10}
    resp = client.post("/webhooks/plaid", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()

    assert data["status"] == "error"
    assert data["code"] == "E_WEBHOOK_INVALID_PAYLOAD"


# -------------------------------------------------------------------------
# Reconcile webhook tests
# -------------------------------------------------------------------------
def test_reconcile_updates_txn_success(client, app):
    with app.app_context():
        user, card = _seed_user_and_card()
        txn = VaultTransaction(
            borrower_id=user.id,
            card_id=card.id,
            amount=100.0,
            method="ACH",
            reconciled=False,
        )
        db.session.add(txn)
        db.session.commit()
        txn_id = txn.id

    payload = {
        "txn_id": txn_id,
        "borrower_id": user.id,
        "card_id": card.id,
    }
    resp = client.post("/webhooks/reconcile", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert data["detail"] == "Reconciliation complete"

    with app.app_context():
        updated = db.session.get(VaultTransaction, txn_id)
        assert updated.reconciled is True
        assert updated.borrower_id == user.id
        assert updated.card_id == card.id


def test_reconcile_returns_not_found_for_missing_txn(client, app):
    with app.app_context():
        user, card = _seed_user_and_card()

    payload = {
        "txn_id": "nonexistent",
        "borrower_id": user.id,
        "card_id": card.id,
    }
    resp = client.post("/webhooks/reconcile", json=payload)
    assert resp.status_code == 404
    data = resp.get_json()

    assert data["status"] == "error"
    assert data["code"] == "E_WEBHOOK_RECONCILE_NOT_FOUND"
