# =============================================================================
# FILE: app/webhooks/views.py
# DESCRIPTION: Production endpoint handlers for ACH, Plaid, and Reconcile webhooks.
#              Enforces cross-tenant data isolation and cryptographic signatures.
# =============================================================================
# app/webhooks/views.py

import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import jwt
import requests
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.borrower_card import BorrowerCard
from app.models.vault_transaction import VaultTransaction

logger = logging.getLogger(__name__)

webhooks = Blueprint("webhooks", __name__)


def _json_object(raw_body: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _verify_hmac_signature(
    secret: str | None,
    signature: str | None,
    raw_body: bytes,
) -> bool:
    """Verify a lowercase/uppercase hex HMAC-SHA256 signature."""
    if not secret or not signature:
        return False

    supplied = signature.removeprefix("sha256=").strip()
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, supplied)


def _verify_plaid_signature(raw_body: bytes) -> bool:
    """Verify Plaid's JWT signature, freshness, and raw-body hash."""
    token = request.headers.get("Plaid-Verification")
    client_id = current_app.config.get("PLAID_CLIENT_ID")
    secret = current_app.config.get("PLAID_SECRET")
    api_base = current_app.config.get("PLAID_API_BASE_URL")

    if not all((token, client_id, secret, api_base)):
        logger.error("Plaid webhook verification is missing configuration")
        return False

    try:
        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        if header.get("alg") != "ES256" or not key_id:
            return False

        response = requests.post(
            f"{api_base.rstrip('/')}/webhook_verification_key/get",
            headers={
                "PLAID-CLIENT-ID": client_id,
                "PLAID-SECRET": secret,
            },
            json={"key_id": key_id},
            timeout=(3, 5),
        )
        response.raise_for_status()
        jwk = response.json()["key"]

        if jwk.get("alg") != "ES256" or jwk.get("kid") != key_id:
            return False

        public_key = jwt.PyJWK.from_dict(jwk).key
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )

        issued_at = claims.get("iat")
        if (
            isinstance(issued_at, bool)
            or not isinstance(issued_at, (int, float))
            or abs(time.time() - issued_at) > 300
        ):
            return False

        body_hash = claims.get("request_body_sha256")
        actual_hash = hashlib.sha256(raw_body).hexdigest()

        return bool(
            isinstance(body_hash, str)
            and hmac.compare_digest(body_hash, actual_hash)
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        jwt.PyJWTError,
        requests.RequestException,
    ):
        logger.warning("Plaid webhook verification failed")
        return False


@webhooks.route("/ach", methods=["POST"])
def ach_webhook():
    raw_body = request.get_data(cache=False)

    if not _verify_hmac_signature(
        current_app.config.get("ACH_WEBHOOK_SECRET"),
        request.headers.get("X-ACH-Signature"),
        raw_body,
    ):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_ACH_INVALID_SIGNATURE",
        }), 401

    payload = _json_object(raw_body)
    if payload is None:
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    borrower_id = payload.get("borrower_id")
    card_id = payload.get("card_id")
    raw_amount = payload.get("amount")

    if not borrower_id or not card_id or raw_amount is None:
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    if isinstance(raw_amount, bool):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    try:
        amount = Decimal(str(raw_amount))
        if not amount.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    card = db.session.get(BorrowerCard, card_id)
    if not card or str(card.user_id) != str(borrower_id):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_TENANT_VIOLATION",
        }), 400

    try:
        txn = VaultTransaction(
            borrower_id=borrower_id,
            card_id=card_id,
            amount=amount,
            method="ACH",
            reconciled=False,
        )
        db.session.add(txn)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to persist ACH webhook transaction")
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_PERSISTENCE_FAILED",
        }), 500

    return jsonify({"status": "ok", "detail": "recorded"}), 200


@webhooks.route("/plaid", methods=["POST"])
def plaid_webhook():
    raw_body = request.get_data(cache=False)

    if not _verify_plaid_signature(raw_body):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_SIGNATURE",
        }), 401

    payload = _json_object(raw_body)
    if payload is None:
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    # Plaid webhooks are event notifications, not borrower/card/amount
    # transaction records. Dispatch to a configured handler that queues the
    # appropriate sync or processing task.
    handler = current_app.extensions.get("plaid_webhook_handler")
    if not callable(handler):
        logger.error("Plaid webhook handler is not configured")
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_HANDLER_UNAVAILABLE",
        }), 503

    try:
        handler(payload)
    except Exception:
        logger.exception("Failed to dispatch Plaid webhook")
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_DISPATCH_FAILED",
        }), 503

    return jsonify({"status": "ok", "detail": "accepted"}), 200


@webhooks.route("/reconcile", methods=["POST"])
def reconcile_webhook():
    raw_body = request.get_data(cache=False)

    if not _verify_hmac_signature(
        current_app.config.get("RECONCILE_WEBHOOK_SECRET"),
        request.headers.get("X-Reconcile-Signature"),
        raw_body,
    ):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_RECONCILE_INVALID_SIGNATURE",
        }), 401

    payload = _json_object(raw_body)
    if payload is None:
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    txn_id = payload.get("txn_id")
    borrower_id = payload.get("borrower_id")
    if not txn_id or not borrower_id:
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_INVALID_PAYLOAD",
        }), 400

    txn = db.session.get(VaultTransaction, txn_id)
    if not txn:
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_RECONCILE_NOT_FOUND",
        }), 404

    if str(txn.borrower_id) != str(borrower_id):
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_TENANT_VIOLATION",
        }), 403

    if txn.reconciled:
        return jsonify({"status": "ok", "detail": "already_complete"}), 200

    try:
        txn.reconciled = True
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to reconcile transaction")
        return jsonify({
            "status": "error",
            "code": "E_WEBHOOK_PERSISTENCE_FAILED",
        }), 500

    return jsonify({"status": "ok", "detail": "complete"}), 200

