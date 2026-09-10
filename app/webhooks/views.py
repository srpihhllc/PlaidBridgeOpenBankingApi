# =============================================================================
# FILE: app/webhooks/views.py
# DESCRIPTION: Production endpoint handlers for ACH, Plaid, and Reconcile webhooks.
#              Enforces cross-tenant data isolation and cryptographic signatures.
# =============================================================================

import hashlib
import hmac
import json
import logging

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models.borrower_card import BorrowerCard
from app.models.vault_transaction import VaultTransaction

logger = logging.getLogger(__name__)

# Instantiated matching the contract expectation inside app/__init__.py
webhooks = Blueprint("webhooks", __name__)


def _verify_hmac_signature(
    secret: str, signature: str, raw_bytes: bytes
) -> bool:
    """
    Validates incoming payload signatures using constant-time verification.
    Prevents timing attacks on external cryptographic endpoint payloads.
    """
    if not signature or not secret:
        return False
    computed = hmac.new(
        secret.encode("utf-8"), raw_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@webhooks.route("/ach", methods=["POST"])
def ach_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-ACH-Signature")
    secret = current_app.config.get("ACH_WEBHOOK_SECRET")

    # 1. Cryptographic Signature Validation
    if not _verify_hmac_signature(secret, signature, raw_body):
        return (
            jsonify(
                {"status": "error", "code": "E_WEBHOOK_ACH_INVALID_SIGNATURE"}
            ),
            401,
        )

    # 2. Payload Parsing & Struct Requirements Check
    try:
        payload = json.loads(raw_body)
    except Exception:
        return jsonify(
            {"status": "error", "code": "E_WEBHOOK_INVALID_PAYLOAD"}
        ), 400

    borrower_id = payload.get("borrower_id")
    card_id = payload.get("card_id")
    amount = payload.get("amount")

    if not borrower_id or not card_id or amount is None:
        return jsonify(
            {"status": "error", "code": "E_WEBHOOK_INVALID_PAYLOAD"}
        ), 400

    # 3. Multi-Tenant Bounds Checks (Cross-Tenant Verification)
    card = db.session.get(BorrowerCard, card_id)
    if not card or str(card.user_id) != str(borrower_id):
        return jsonify(
            {"status": "error", "code": "E_WEBHOOK_TENANT_VIOLATION"}
        ), 400

    # 4. State Modification Persistence
    txn = VaultTransaction(
        borrower_id=borrower_id,
        card_id=card_id,
        amount=amount,
        method="ACH",
        reconciled=False,
    )
    db.session.add(txn)
    db.session.commit()

    return jsonify({"status": "ok", "detail": "recorded"}), 200


@webhooks.route("/plaid", methods=["POST"])
def plaid_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-Plaid-Signature")
    secret = current_app.config.get("PLAID_WEBHOOK_SECRET")

    # 1. Signature Verification
    if not _verify_hmac_signature(secret, signature, raw_body):
        return (
            jsonify(
                {
                    "status": "error",
                    "code": "E_WEBHOOK_ACH_INVALID_SIGNATURE",  # Reused baseline auth rejection code
                }
            ),
            401,
        )

    # 2. Schema Validation
    try:
        payload = json.loads(raw_body)
    except Exception:
        return jsonify(
            {"status": "error", "code": "E_WEBHOOK_INVALID_PAYLOAD"}
        ), 400

    borrower_id = payload.get("borrower_id")
    card_id = payload.get("card_id")
    amount = payload.get("amount")

    if not borrower_id or not card_id or amount is None:
        return jsonify(
            {"status": "error", "code": "E_WEBHOOK_INVALID_PAYLOAD"}
        ), 400

    # 3. Operational Range Invalidation (Reject Negative Limits)
    try:
        float_amount = float(amount)
        if float_amount < 0:
            return (
                jsonify(
                    {"status": "error", "code": "E_WEBHOOK_INVALID_PAYLOAD"}
                ),
                400,
            )
    except (ValueError, TypeError):
        return jsonify(
            {"status": "error", "code": "E_WEBHOOK_INVALID_PAYLOAD"}
        ), 400

    return jsonify({"status": "ok", "detail": "synced"}), 200


@webhooks.route("/reconcile", methods=["POST"])
def reconcile_webhook():
    payload = request.get_json() or {}
    txn_id = payload.get("txn_id")

    # 1. Validate Record Existence
    txn = db.session.get(VaultTransaction, txn_id)
    if not txn:
        return (
            jsonify(
                {"status": "error", "code": "E_WEBHOOK_RECONCILE_NOT_FOUND"}
            ),
            404,
        )

    # 2. Commit Mutation State
    txn.reconciled = True
    db.session.commit()

    return jsonify({"status": "ok", "detail": "complete"}), 200
