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
import sqlalchemy as sa

from app import create_app, db
from app.models.borrower_card import BorrowerCard
from app.models.user import User
from app.models.vault_transaction import VaultTransaction


@pytest.fixture
def app():
    application = create_app("app.config.TestConfig")
    with application.app_context():
        db.create_all()
        yield application
        # MySQL requires FK checks to be disabled before drop_all;
        # SQLite ignores these statements, so this is safe for both dialects.
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
    """Helper to create a valid borrower and card.

    BorrowerCard NOT NULL columns (no default): user_id, card_number,
    expiration_date, cvv, score, color.
    Returns plain scalar ids, not ORM instances, to avoid DetachedInstanceError
    when the caller exits the app_context.
    """
    user = User(
        email="borrower@example.com",
        password_hash="test",
    )
    db.session.add(user)
    db.session.flush()  # populate user.id without committing

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

    # Return plain scalars — safe to use outside the app_context
    return str(user.id), int(card.id)


# -------------------------------------------------------------------------
# ACH webhook tests
# -------------------------------------------------------------------------
def test_ach_listener_creates_txn_success(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": 50.0}
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
        assert txns[0].borrower_id == user_id
        assert txns[0].card_id == card_id


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
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": "75.0"}
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
        assert txns[0].borrower_id == user_id
        assert txns[0].card_id == card_id


def test_plaid_listener_rejects_invalid_amount(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {"borrower_id": user_id, "card_id": card_id, "amount": -10}
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
        txn_id = txn.id  # capture scalar before context exits

    payload = {
        "txn_id": txn_id,
        "borrower_id": user_id,
        "card_id": card_id,
    }
    resp = client.post("/webhooks/reconcile", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["status"] == "ok"
    assert data["detail"] == "Reconciliation complete"

    with app.app_context():
        updated = db.session.get(VaultTransaction, txn_id)
        assert updated.reconciled is True
        assert updated.borrower_id == user_id
        assert updated.card_id == card_id


def test_reconcile_returns_not_found_for_missing_txn(client, app):
    with app.app_context():
        user_id, card_id = _seed_user_and_card()

    payload = {
        "txn_id": "nonexistent",
        "borrower_id": user_id,
        "card_id": card_id,
    }
    resp = client.post("/webhooks/reconcile", json=payload)
    assert resp.status_code == 404
    data = resp.get_json()

    assert data["status"] == "error"
    assert data["code"] == "E_WEBHOOK_RECONCILE_NOT_FOUND"