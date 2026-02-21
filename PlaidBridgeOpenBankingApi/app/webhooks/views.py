# =============================================================================
# FILE: app/webhooks/views.py
# DESCRIPTION:
#   Cockpit-grade Webhooks blueprint for ACH, Plaid, and reconciliation events.
#
#   Provides:
#     1. Payload validation layer
#        - Required fields
#        - Type checking
#        - Schema enforcement
#        - Error codes
#        - Operator-friendly messages
#
#     2. Idempotency layer
#        - Prevent duplicate ACH/Plaid events
#        - Prevent duplicate reconciliation
#        - Redis-based idempotency keys
#        - TTL-bound replay protection
#
#     3. Telemetry layer
#        - WEBHOOK_ACH_RECEIVED
#        - WEBHOOK_ACH_VALIDATION_FAILED
#        - WEBHOOK_ACH_RECORDED
#        - WEBHOOK_ACH_DB_ERROR
#        - WEBHOOK_PLAID_RECEIVED
#        - WEBHOOK_PLAID_RECORDED
#        - WEBHOOK_RECONCILE_ATTEMPT
#        - WEBHOOK_RECONCILE_SUCCESS
#        - WEBHOOK_RECONCILE_FAILURE
#        - WEBHOOK_REDIS_UNAVAILABLE
#
#     4. Redis trace emission
#        - TTL-bound
#        - Namespaced keys
#        - JSON-encoded
#        - Operator-friendly
#
#     5. Signature verification (optional)
#        - HMAC header validation
#        - Shared secret
#        - Replay protection (via idempotency keys)
#
#     6. DB safety
#        - Rollback on error
#        - Explicit commit paths
#        - Error codes
#
#     7. Contract enforcement
#        - Strict JSON schema
#        - Missing fields
#        - Invalid types
#        - Negative amounts
#        - Invalid borrower/card IDs
#
#     8. Operator-grade error codes
#        - E_WEBHOOK_ACH_DB_COMMIT_FAILED
#        - E_WEBHOOK_PLAID_DB_COMMIT_FAILED
#        - E_WEBHOOK_RECONCILE_NOT_FOUND
#        - E_WEBHOOK_RECONCILE_DB_ERROR
#        - E_WEBHOOK_REDIS_UNAVAILABLE
#        - E_WEBHOOK_INVALID_PAYLOAD
#
#     9. Audit logging
#        - IP address
#        - Event type
#        - Payload hash
#        - Timestamp
#
#    10. VaultTransaction safety
#        - Validate borrower exists
#        - Validate card exists
#        - Validate amount > 0
#        - Validate txn exists before reconcile
# =============================================================================

import hashlib
import hmac
import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models.borrower_card import BorrowerCard
from app.models.user import User
from app.models.vault_transaction import VaultTransaction
from app.utils.redis_utils import get_redis_client
from app.utils.telemetry import log_identity_event

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
WEBHOOK_TTL_SECONDS = 3600  # 1 hour TTL for traces & idempotency keys
IDEMPOTENCY_PREFIX = "webhook:idempotency"
TRACE_PREFIX = "webhook:trace"

# Optional shared secrets (read from config)
ACH_WEBHOOK_SECRET_CONFIG_KEY = "ACH_WEBHOOK_SECRET"
PLAID_WEBHOOK_SECRET_CONFIG_KEY = "PLAID_WEBHOOK_SECRET"

# Header names for signatures (can be adjusted to provider-specific headers)
ACH_SIGNATURE_HEADER = "X-ACH-Signature"
PLAID_SIGNATURE_HEADER = "X-Plaid-Signature"


# -----------------------------------------------------------------------------
# JSON helpers
# -----------------------------------------------------------------------------
def _json_error(code: str, http_status: int, message: str, extra: dict | None = None):
    payload = {
        "status": "error",
        "code": code,
        "message": message,
    }
    if extra:
        payload["extra"] = extra
    return jsonify(payload), http_status


def _json_ok(data: dict | None = None, http_status: int = 200):
    payload = {"status": "ok"}
    if data:
        payload.update(data)
    return jsonify(payload), http_status


# -----------------------------------------------------------------------------
# Signature verification
# -----------------------------------------------------------------------------
def _verify_signature(secret: str | None, header_signature: str | None, body: bytes) -> bool:
    """
    Verifies HMAC signature if a secret is provided.
    If no secret is configured, returns True (no-op).
    """
    if not secret:
        # Signature verification not configured in this environment
        return True

    if not header_signature:
        return False

    try:
        computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, header_signature)
    except Exception as exc:
        current_app.logger.error(f"❌ Signature verification failure: {exc}", exc_info=True)
        return False


# -----------------------------------------------------------------------------
# Schema / payload validation
# -----------------------------------------------------------------------------
def _validate_required_fields(required_keys: list[str], payload: dict) -> list[str]:
    return [k for k in required_keys if payload.get(k) is None]


def _validate_schema(schema: dict[str, type], payload: dict) -> list[str]:
    """
    schema: { "field_name": expected_type }
    Returns list of fields that fail type checks.
    """
    invalid = []
    for field, expected_type in schema.items():
        if field not in payload:
            continue  # missing handled separately
        value = payload[field]
        if value is None:
            invalid.append(field)
            continue
        # Allow numeric strings for float/int fields; we cast later.
        if expected_type in (int, float) and isinstance(value, str):
            try:
                expected_type(value)  # test cast
            except Exception:
                invalid.append(field)
        elif not isinstance(value, expected_type):
            invalid.append(field)
    return invalid


def _validate_amount_positive(amount_raw) -> bool:
    try:
        amount = float(amount_raw)
        return amount > 0
    except Exception:
        return False


# -----------------------------------------------------------------------------
# VaultTransaction safety helpers
# -----------------------------------------------------------------------------
def _borrower_exists(borrower_id) -> bool:
    if not borrower_id:
        return False
    try:
        return db.session.get(User, borrower_id) is not None
    except Exception as exc:
        current_app.logger.error(f"❌ Error checking borrower existence: {exc}", exc_info=True)
        return False


def _card_exists(card_id) -> bool:
    if not card_id:
        return False
    try:
        return db.session.get(BorrowerCard, card_id) is not None
    except Exception as exc:
        current_app.logger.error(f"❌ Error checking card existence: {exc}", exc_info=True)
        return False


# -----------------------------------------------------------------------------
# Idempotency helpers
# -----------------------------------------------------------------------------
def _get_body_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body or b"").hexdigest()


def _is_duplicate_event(redis, provider: str, raw_body: bytes) -> bool:
    """
    Uses a hash of the request body as an idempotency key.
    If key exists in Redis, event is considered already processed.
    """
    body_hash = _get_body_hash(raw_body)
    key = f"{IDEMPOTENCY_PREFIX}:{provider}:{body_hash}"

    try:
        created = redis.set(key, "1", nx=True, ex=WEBHOOK_TTL_SECONDS)
        # If set() returns True/1 => new key created => not duplicate
        # If None => key already exists => duplicate
        return not bool(created)
    except Exception as exc:
        current_app.logger.warning(f"⚠️ Redis unavailable for idempotency: {exc}", exc_info=True)
        _emit_webhook_trace(
            event_type="WEBHOOK_REDIS_UNAVAILABLE",
            provider=provider,
            payload={},
            status="redis_unavailable",
        )
        # Do NOT treat as duplicate on Redis failure; process normally
        return False


# -----------------------------------------------------------------------------
# Redis trace emission
# -----------------------------------------------------------------------------
def _emit_webhook_trace(event_type: str, provider: str, payload: dict, status: str):
    """
    Emits a short-lived trace to Redis for cockpit inspection.
    Payload is not fully stored; we use a hash and minimal metadata.
    """
    trace = {
        "event_type": event_type,
        "provider": provider,
        "status": status,
        "timestamp": int(datetime.utcnow().timestamp()),
        "ip": request.remote_addr,
    }

    # Safe payload hash (no PII)
    try:
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    except Exception:
        payload_hash = None
    trace["payload_hash"] = payload_hash

    try:
        redis = get_redis_client()
        key = f"{TRACE_PREFIX}:{provider}:{event_type}:{trace['timestamp']}"
        redis.setex(key, WEBHOOK_TTL_SECONDS, json.dumps(trace))
    except Exception as exc:
        current_app.logger.warning(
            f"⚠️ Redis unavailable during webhook trace emit: {exc}", exc_info=True
        )
        # This is non-fatal to the request path.


# -----------------------------------------------------------------------------
# Common audit logging helper
# -----------------------------------------------------------------------------
def _log_webhook_identity(event_type: str):
    log_identity_event(
        user_id=None,
        event_type=event_type,
        details={"ip": request.remote_addr},
        ip=request.remote_addr,
    )


# =============================================================================
# ACH Webhook
# =============================================================================
@webhooks_bp.route("/ach", methods=["POST"])
def ach_listener():
    raw_body = request.get_data(cache=False) or b""
    payload = request.get_json(silent=True) or {}

    _log_webhook_identity("WEBHOOK_ACH_RECEIVED")

    # Optional signature verification
    secret = current_app.config.get(ACH_WEBHOOK_SECRET_CONFIG_KEY)
    header_sig = request.headers.get(ACH_SIGNATURE_HEADER)
    if not _verify_signature(secret, header_sig, raw_body):
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_VALIDATION_FAILED",
            provider="ACH",
            payload=payload,
            status="invalid_signature",
        )
        return _json_error(
            code="E_WEBHOOK_ACH_INVALID_SIGNATURE",
            http_status=401,
            message="Invalid ACH webhook signature.",
        )

    # Idempotency via Redis
    try:
        redis = get_redis_client()
    except Exception as exc:
        current_app.logger.warning(f"⚠️ Redis unavailable for ACH idempotency: {exc}", exc_info=True)
        redis = None
        _emit_webhook_trace(
            event_type="WEBHOOK_REDIS_UNAVAILABLE",
            provider="ACH",
            payload={},
            status="redis_unavailable",
        )

    if redis and _is_duplicate_event(redis, "ACH", raw_body):
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_RECORDED",
            provider="ACH",
            payload=payload,
            status="duplicate_ignored",
        )
        return _json_ok({"detail": "duplicate_event_ignored"})

    # Schema & payload validation
    required_fields = ["borrower_id", "card_id", "amount"]
    missing = _validate_required_fields(required_fields, payload)
    if missing:
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_VALIDATION_FAILED",
            provider="ACH",
            payload=payload,
            status="missing_fields",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Missing required fields.",
            extra={"missing_fields": missing},
        )

    schema = {
        "borrower_id": str,
        "card_id": str,
        "amount": (int, float, str),
    }
    invalid = _validate_schema(schema, payload)
    if invalid:
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_VALIDATION_FAILED",
            provider="ACH",
            payload=payload,
            status="invalid_types",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid field types.",
            extra={"invalid_fields": invalid},
        )

    if not _validate_amount_positive(payload["amount"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_VALIDATION_FAILED",
            provider="ACH",
            payload=payload,
            status="invalid_amount",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Amount must be positive.",
        )

    # VaultTransaction safety: borrower and card existence
    if not _borrower_exists(payload["borrower_id"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_VALIDATION_FAILED",
            provider="ACH",
            payload=payload,
            status="invalid_borrower",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid borrower_id.",
        )

    if not _card_exists(payload["card_id"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_VALIDATION_FAILED",
            provider="ACH",
            payload=payload,
            status="invalid_card",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid card_id.",
        )

    # DB write path
    try:
        amount = float(payload["amount"])
        txn = VaultTransaction(
            borrower_id=payload["borrower_id"],
            card_id=payload["card_id"],
            amount=amount,
            method="ACH",
            reconciled=False,
        )
        db.session.add(txn)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"❌ ACH webhook DB error: {exc}", exc_info=True)
        _emit_webhook_trace(
            event_type="WEBHOOK_ACH_DB_ERROR",
            provider="ACH",
            payload=payload,
            status="db_error",
        )
        return _json_error(
            code="E_WEBHOOK_ACH_DB_COMMIT_FAILED",
            http_status=500,
            message="Failed to record ACH transaction.",
        )

    _emit_webhook_trace(
        event_type="WEBHOOK_ACH_RECORDED",
        provider="ACH",
        payload=payload,
        status="recorded",
    )
    return _json_ok({"detail": "ACH transaction recorded"})


# =============================================================================
# Plaid Webhook
# =============================================================================
@webhooks_bp.route("/plaid", methods=["POST"])
def plaid_listener():
    raw_body = request.get_data(cache=False) or b""
    payload = request.get_json(silent=True) or {}

    _log_webhook_identity("WEBHOOK_PLAID_RECEIVED")

    # Optional signature verification
    secret = current_app.config.get(PLAID_WEBHOOK_SECRET_CONFIG_KEY)
    header_sig = request.headers.get(PLAID_SIGNATURE_HEADER)
    if not _verify_signature(secret, header_sig, raw_body):
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_VALIDATION_FAILED",
            provider="Plaid",
            payload=payload,
            status="invalid_signature",
        )
        return _json_error(
            code="E_WEBHOOK_PLAID_INVALID_SIGNATURE",
            http_status=401,
            message="Invalid Plaid webhook signature.",
        )

    # Idempotency via Redis
    try:
        redis = get_redis_client()
    except Exception as exc:
        current_app.logger.warning(
            f"⚠️ Redis unavailable for Plaid idempotency: {exc}", exc_info=True
        )
        redis = None
        _emit_webhook_trace(
            event_type="WEBHOOK_REDIS_UNAVAILABLE",
            provider="Plaid",
            payload={},
            status="redis_unavailable",
        )

    if redis and _is_duplicate_event(redis, "Plaid", raw_body):
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_RECORDED",
            provider="Plaid",
            payload=payload,
            status="duplicate_ignored",
        )
        return _json_ok({"detail": "duplicate_event_ignored"})

    # Schema & payload validation
    required_fields = ["borrower_id", "card_id", "amount"]
    missing = _validate_required_fields(required_fields, payload)
    if missing:
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_VALIDATION_FAILED",
            provider="Plaid",
            payload=payload,
            status="missing_fields",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Missing required fields.",
            extra={"missing_fields": missing},
        )

    schema = {
        "borrower_id": str,
        "card_id": str,
        "amount": (int, float, str),
    }
    invalid = _validate_schema(schema, payload)
    if invalid:
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_VALIDATION_FAILED",
            provider="Plaid",
            payload=payload,
            status="invalid_types",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid field types.",
            extra={"invalid_fields": invalid},
        )

    if not _validate_amount_positive(payload["amount"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_VALIDATION_FAILED",
            provider="Plaid",
            payload=payload,
            status="invalid_amount",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Amount must be positive.",
        )

    # VaultTransaction safety: borrower and card existence
    if not _borrower_exists(payload["borrower_id"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_VALIDATION_FAILED",
            provider="Plaid",
            payload=payload,
            status="invalid_borrower",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid borrower_id.",
        )

    if not _card_exists(payload["card_id"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_VALIDATION_FAILED",
            provider="Plaid",
            payload=payload,
            status="invalid_card",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid card_id.",
        )

    # DB write path
    try:
        amount = float(payload["amount"])
        txn = VaultTransaction(
            borrower_id=payload["borrower_id"],
            card_id=payload["card_id"],
            amount=amount,
            method="Plaid",
            reconciled=False,
        )
        db.session.add(txn)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"❌ Plaid webhook DB error: {exc}", exc_info=True)
        _emit_webhook_trace(
            event_type="WEBHOOK_PLAID_DB_ERROR",
            provider="Plaid",
            payload=payload,
            status="db_error",
        )
        return _json_error(
            code="E_WEBHOOK_PLAID_DB_COMMIT_FAILED",
            http_status=500,
            message="Failed to record Plaid transaction.",
        )

    _emit_webhook_trace(
        event_type="WEBHOOK_PLAID_RECORDED",
        provider="Plaid",
        payload=payload,
        status="recorded",
    )
    return _json_ok({"detail": "Plaid transaction recorded"})


# =============================================================================
# Reconciliation Webhook
# =============================================================================
@webhooks_bp.route("/reconcile", methods=["POST"])
def reconcile_payments():
    raw_body = request.get_data(cache=False) or b""
    payload = request.get_json(silent=True) or {}

    _log_webhook_identity("WEBHOOK_RECONCILE_ATTEMPT")

    # Idempotency for reconciliation
    try:
        redis = get_redis_client()
    except Exception as exc:
        current_app.logger.warning(
            f"⚠️ Redis unavailable for reconcile idempotency: {exc}", exc_info=True
        )
        redis = None
        _emit_webhook_trace(
            event_type="WEBHOOK_REDIS_UNAVAILABLE",
            provider="Reconcile",
            payload={},
            status="redis_unavailable",
        )

    if redis and _is_duplicate_event(redis, "Reconcile", raw_body):
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_SUCCESS",
            provider="Reconcile",
            payload=payload,
            status="duplicate_ignored",
        )
        return _json_ok({"detail": "duplicate_event_ignored"})

    # Schema & payload validation
    required_fields = ["txn_id", "borrower_id", "card_id"]
    missing = _validate_required_fields(required_fields, payload)
    if missing:
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_FAILURE",
            provider="Reconcile",
            payload=payload,
            status="missing_fields",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Missing required fields.",
            extra={"missing_fields": missing},
        )

    schema = {
        "txn_id": (int, str),
        "borrower_id": str,
        "card_id": str,
    }
    invalid = _validate_schema(schema, payload)
    if invalid:
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_FAILURE",
            provider="Reconcile",
            payload=payload,
            status="invalid_types",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid field types.",
            extra={"invalid_fields": invalid},
        )

    # VaultTransaction safety: borrower and card existence
    if not _borrower_exists(payload["borrower_id"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_FAILURE",
            provider="Reconcile",
            payload=payload,
            status="invalid_borrower",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid borrower_id.",
        )

    if not _card_exists(payload["card_id"]):
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_FAILURE",
            provider="Reconcile",
            payload=payload,
            status="invalid_card",
        )
        return _json_error(
            code="E_WEBHOOK_INVALID_PAYLOAD",
            http_status=400,
            message="Invalid card_id.",
        )

    # Load transaction
    txn_id = str(payload["txn_id"])
    txn = db.session.get(VaultTransaction, txn_id)
    if not txn:
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_FAILURE",
            provider="Reconcile",
            payload=payload,
            status="not_found",
        )
        return _json_error(
            code="E_WEBHOOK_RECONCILE_NOT_FOUND",
            http_status=404,
            message="Transaction not found.",
        )

    # DB update path
    try:
        txn.borrower_id = payload["borrower_id"]
        txn.card_id = payload["card_id"]
        txn.reconciled = True
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"❌ DB error during reconcile: {exc}", exc_info=True)
        _emit_webhook_trace(
            event_type="WEBHOOK_RECONCILE_FAILURE",
            provider="Reconcile",
            payload=payload,
            status="db_error",
        )
        return _json_error(
            code="E_WEBHOOK_RECONCILE_DB_ERROR",
            http_status=500,
            message="Failed to reconcile transaction.",
        )

    _emit_webhook_trace(
        event_type="WEBHOOK_RECONCILE_SUCCESS",
        provider="Reconcile",
        payload=payload,
        status="reconciled",
    )
    return _json_ok({"detail": "Reconciliation complete"})
