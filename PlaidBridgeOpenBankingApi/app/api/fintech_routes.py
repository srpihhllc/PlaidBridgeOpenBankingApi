# =============================================================================
# FILE: app/api/fintech_routes.py
# DESCRIPTION: Blueprint exposing FinTech verification, lender trust-gate
#              workflows, and Transaction CRUD endpoints.
# NOTES:
# - Mounted by a higher-level blueprint (e.g., /api/v1) for final URL paths.
# - Verification endpoints (TrueLayer, Tink) are nested under /fintech/.
# - Lender flows are under /lenders and /link/manual.
# - Transaction endpoints (GET/POST /transactions) are at the blueprint root.
# =============================================================================

import base64
import logging
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, get_jwt_identity, jwt_required
from werkzeug.exceptions import BadRequest, Forbidden, NotFound, Unauthorized

from app.api.validation import validate_json_schema
from app.extensions import csrf, db, limiter
from app.models import Transaction
from app.models.bank_account import BankAccount
from app.models.lender import Lender
from app.models.mfa_code import MFACode
from app.models.plaid_item import PlaidItem
from app.models.schema_event import SchemaEvent
from app.models.user import User
from app.services import fintech_api
from app.services.mock_data_service import MockDataService
from app.utils.telemetry import increment_counter

logger = logging.getLogger(__name__)
_logger = logger


# --- Rate Limit Guard (Deferred to Request Time) ---
def _rate_limit(limit_str: str):
    """
    Safe rate limit decorator that defers ALL context checks to request time.

    CRITICAL: This decorator does NOT access current_app at decoration time.
    Instead, it returns a wrapper function that:
    1. Checks RATE_LIMIT_ENABLED and TESTING at request time (when context exists)
    2. Only applies limiter.limit() if rate limiting should be active

    This completely avoids the "Working outside of application context" error.

    Usage:
        @_rate_limit("20/hour")
        def my_route():
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # At REQUEST TIME, check if we should apply rate limiting
            # (current_app context is guaranteed to exist here)

            # Check if rate limiting is disabled globally
            if not current_app.config.get("RATE_LIMIT_ENABLED", True):
                return func(*args, **kwargs)

            # Check if we're in testing mode
            if current_app.config.get("TESTING"):
                return func(*args, **kwargs)

            # Rate limiting is enabled: apply the limiter at request time
            rate_limited_func = limiter.limit(limit_str)(func)
            return rate_limited_func(*args, **kwargs)

        return wrapper

    return decorator


# -----------------------------------------------------------------------------
# Blueprint definition
# -----------------------------------------------------------------------------
fintech_bp = Blueprint("fintech_api_bp", __name__)
csrf.exempt(fintech_bp)


# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------


@fintech_bp.errorhandler(BadRequest)
def handle_bad_request(e):
    """Override default 400 for invalid/missing JSON with 422."""
    return jsonify({"error": "Request must be JSON"}), 422


# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------


def _parse_json(required_fields: dict[str, str] | None = None) -> dict[str, Any]:
    """Parse request JSON and enforce required fields if provided."""
    try:
        payload = request.get_json(force=True, silent=False)
    except BadRequest as exc:
        raise BadRequest("Invalid JSON: unable to parse request body.") from exc

    if not isinstance(payload, dict):
        raise BadRequest("Invalid JSON: expected an object at the top level.")

    missing = []
    if required_fields:
        for field, desc in required_fields.items():
            if field not in payload or payload[field] in (None, "", []):
                missing.append(f"{field} ({desc})")
    if missing:
        raise BadRequest(f"Missing required fields: {', '.join(missing)}")

    return payload


def _json():
    """Simpler JSON helper for lender/link flows."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Invalid JSON payload.")
    return data


def _envelope_success(data: dict[str, Any]) -> tuple:
    """Wrap response data in success envelope."""
    return jsonify({"status": "success", "data": data}), 200


def _envelope_error(message: str, vendor: str | None = None, code: int | None = None) -> tuple:
    """Standardized error envelope with optional vendor and HTTP code override."""
    return (
        jsonify(
            {
                "status": "error",
                "error": {
                    "code": "E_VENDOR" if vendor else "E_INPUT",
                    "message": message,
                    "vendor": vendor,
                },
            }
        ),
        code or (400 if vendor else 422),
    )


def _assert_lender_verified(lender: Lender):
    """Verify lender is authenticated and verified before allowing access."""
    if not lender or not lender.is_verified:
        increment_counter("lender_not_verified_block")
        raise Forbidden("Lender must be verified and linked before requesting access.")


def _emit_event(user_id: int, event_type: str, detail: str, origin: str = "api"):
    """Record an audit event to the database."""
    db.session.add(
        SchemaEvent(
            user_id=user_id,
            event_type=event_type,
            detail=detail,
            origin=origin,
            timestamp=datetime.utcnow(),
        )
    )


# =============================================================================
# 1. FINTECH VERIFICATION ROUTES
# =============================================================================


@fintech_bp.route("/fintech/health", methods=["GET"])
def health():
    """Lightweight health probe for the combined API blueprint."""
    routes = [rule.rule for rule in current_app.url_map.iter_rules()]
    return jsonify({"status": "ok", "routes": routes}), 200


@fintech_bp.route("/fintech/verify/truelayer", methods=["POST"])
@csrf.exempt
def verify_truelayer():
    """Verify account via TrueLayer provider."""
    try:
        payload = _parse_json()
    except BadRequest as e:
        return _envelope_error(str(e))

    result = fintech_api.verify_via_truelayer(payload)
    if isinstance(result, dict) and "error" in result:
        _logger.warning("TrueLayer verification error: %s", result["error"])
        return _envelope_error(result["error"], vendor="TrueLayer")

    return _envelope_success(result if isinstance(result, dict) else {"result": result})


@fintech_bp.route("/fintech/verify/tink", methods=["POST"])
@csrf.exempt
def verify_tink():
    """Verify account via Tink provider."""
    try:
        payload = _parse_json()
    except BadRequest as e:
        return _envelope_error(str(e))

    result = fintech_api.verify_via_tink(payload)
    if isinstance(result, dict) and "error" in result:
        _logger.warning("Tink verification error: %s", result["error"])
        return _envelope_error(result["error"], vendor="Tink")

    return _envelope_success(result if isinstance(result, dict) else {"result": result})


# =============================================================================
# 2. LENDER SELF-LINKING (TRUST GATE) + MANUAL LINK FLOWS
# =============================================================================


@fintech_bp.route("/lenders/link", methods=["POST"])
@jwt_required()
@_rate_limit("20/hour")
@csrf.exempt
def lender_self_link():
    """
    Lender verifies and links their own institutional account.

    This is the trust gate before any subscriber access requests.
    Includes AI + Compliance + Fraud + Ethics verification.

    Request JSON:
        {
            "aggregator": "plaid" | "truelayer" | "tink" | null,
            "institution_name": "string",
            "external_item_id": "string",
            "manual_meta": {
                "institution": "string",
                "account_number": "string",
                "routing_number": "string",
                "initial_balance": number
            }
        }
    """
    data = _json()
    lender = Lender.query.filter_by(user_id=current_user.id).first()
    if not lender:
        raise Unauthorized("Lender profile not found for current user.")

    aggregator = data.get("aggregator")  # "plaid" | "truelayer" | "tink" | None
    manual_meta = data.get("manual_meta")  # dict with institution details

    try:
        # Persist a minimal link artifact; in real flow call your service layer
        if aggregator in ("plaid", "truelayer", "tink"):
            item = PlaidItem(
                user_id=current_user.id,
                institution_name=data.get("institution_name") or aggregator,
                external_item_id=data.get("external_item_id"),
            )
            db.session.add(item)

        elif manual_meta:
            acct = BankAccount(
                user_id=current_user.id,
                institution=manual_meta.get("institution"),
                account_number=manual_meta.get("account_number"),
                routing_number=manual_meta.get("routing_number"),
                balance=manual_meta.get("initial_balance", 0.0),
            )
            db.session.add(acct)

        else:
            raise BadRequest("Provide 'aggregator' or 'manual_meta' for lender linking.")

        # AI + Compliance + Fraud + Ethics verification BEFORE marking verified
        from app.compliance import check_lender_compliance
        from app.compliance_ai import predict_fraud_trends
        from app.services.symphony_ai import SymphonyAI
        from app.utils import notify_authorities

        fraud_trends = predict_fraud_trends()
        compliance = check_lender_compliance(lender.id)

        ai_brain = SymphonyAI()
        risk_report = ai_brain.run(
            instruction=f"Evaluate lender {lender.id} for fraud, ethics, and compliance risk.",
            user_id=lender.user_id,
        )

        # Decision logic
        if fraud_trends.get("status") == "high risk" or compliance.get("violations", 0) > 3:
            notify_authorities(
                "Lender Risk Alert",
                {
                    "lender_id": lender.id,
                    "fraud_trends": fraud_trends,
                    "compliance": compliance,
                    "ai_report": risk_report,
                },
            )
            increment_counter("lender_self_link_blocked_risk")
            raise Forbidden("Lender failed compliance and fraud checks.")

        # Only mark verified AFTER passing all checks
        lender.is_verified = True

        _emit_event(
            user_id=current_user.id,
            event_type="LENDER_SELF_LINKED",
            detail=f"Lender linked via {aggregator or 'manual'}",
            origin="lender_link",
        )
        db.session.commit()
        increment_counter("lender_self_link_success")

        return (
            jsonify(
                {
                    "status": "success",
                    "msg": "Lender account linked and verified after compliance checks.",
                    "lender_verified": True,
                }
            ),
            201,
        )

    except Forbidden as exc:
        db.session.rollback()
        _logger.warning("Lender self-link blocked: %s", exc)
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": "E_LENDER_RISK",
                        "message": str(exc),
                    },
                }
            ),
            403,
        )

    except Exception as exc:
        db.session.rollback()
        _logger.exception("Lender self-link failed: %s", exc)
        increment_counter("lender_self_link_fail")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {"code": "E_LINK", "message": "Failed to link lender"},
                }
            ),
            500,
        )


@fintech_bp.route("/link/manual/request", methods=["POST"])
@jwt_required()
@_rate_limit("60/hour")
@csrf.exempt
def request_manual_link():
    """
    Lender requests access to a subscriber's account.

    Requires lender to be verified (self-linked).

    Request JSON:
        {
            "subscriber_id": number,
            "reason": "string (optional)"
        }
    """
    data = _json()
    subscriber_id = data.get("subscriber_id")
    reason = data.get("reason", "unspecified")

    lender = Lender.query.filter_by(user_id=current_user.id).first()
    _assert_lender_verified(lender)

    subscriber = User.query.get(subscriber_id)
    if not subscriber:
        raise NotFound("Subscriber not found.")

    try:
        _emit_event(
            user_id=subscriber.id,
            event_type="LINK_REQUESTED",
            detail=f"Lender {current_user.id} requested access. Reason: {reason}",
            origin="lender_request",
        )
        db.session.commit()
        increment_counter("link_request_created")

        return (
            jsonify(
                {
                    "status": "success",
                    "msg": "Link request submitted. Awaiting subscriber approval.",
                    "subscriber_id": subscriber.id,
                }
            ),
            202,
        )

    except Exception as exc:
        db.session.rollback()
        _logger.exception("Manual link request failed: %s", exc)
        increment_counter("link_request_fail")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": "E_REQUEST",
                        "message": "Failed to submit link request",
                    },
                }
            ),
            500,
        )


@fintech_bp.route("/link/manual/approve", methods=["POST"])
@jwt_required()
@_rate_limit("30/hour")
@csrf.exempt
def approve_manual_link():
    """
    Subscriber approves a pending lender request.

    Issues a one-time code the lender must redeem to finalize the link.

    Request JSON:
        {
            "lender_user_id": number,
            "ttl_seconds": number (optional, default: 300)
        }
    """
    data = _json()
    lender_user_id = data.get("lender_user_id")
    ttl_seconds = int(data.get("ttl_seconds", 300))

    if not lender_user_id:
        raise BadRequest("Missing 'lender_user_id'.")

    subscriber_id = get_jwt_identity()

    try:
        code = MFACode(
            user_id=subscriber_id,
            code_type="link_code",
            code_value=MFACode.generate_code(length=10),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
            metadata={"lender_user_id": lender_user_id},
        )
        db.session.add(code)

        _emit_event(
            user_id=subscriber_id,
            event_type="LINK_APPROVED_CODE_ISSUED",
            detail=f"One-time code issued for lender {lender_user_id}",
            origin="subscriber_approve",
        )
        db.session.commit()
        increment_counter("link_code_issued")

        return (
            jsonify(
                {
                    "status": "success",
                    "msg": (
                        "Approval recorded. Provide this code to the lender to " "complete linking."
                    ),
                    "link_code": code.code_value,
                    "expires_at": code.expires_at.isoformat() + "Z",
                }
            ),
            201,
        )

    except Exception as exc:
        db.session.rollback()
        _logger.exception("Approval code issuance failed: %s", exc)
        increment_counter("link_code_issue_fail")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": "E_CODE",
                        "message": "Failed to issue approval code",
                    },
                }
            ),
            500,
        )


@fintech_bp.route("/link/manual/redeem", methods=["POST"])
@jwt_required()
@_rate_limit("30/hour")
@csrf.exempt
def redeem_manual_link():
    """
    Lender redeems the subscriber-issued one-time code to finalize the link.

    Creates a shared link artifact (e.g., association record).

    Request JSON:
        {
            "code": "string"
        }
    """
    data = _json()
    code_value = data.get("code")
    if not code_value:
        raise BadRequest("Missing 'code'.")

    lender = Lender.query.filter_by(user_id=current_user.id).first()
    _assert_lender_verified(lender)

    code = MFACode.query.filter_by(code_value=code_value, code_type="link_code").first()
    if not code:
        increment_counter("link_code_not_found")
        raise NotFound("Link approval code not found.")
    if code.is_expired():
        increment_counter("link_code_expired")
        raise Forbidden("Link approval code has expired.")

    subscriber = User.query.get(code.user_id)
    if not subscriber:
        raise NotFound("Subscriber tied to approval code not found.")

    try:
        assoc_note = (
            f"Manual link established between lender {current_user.id} "
            f"and subscriber {subscriber.id}"
        )
        _emit_event(
            user_id=subscriber.id,
            event_type="LINK_FINALIZED",
            detail=assoc_note,
            origin="lender_redeem",
        )

        code.mark_used()
        db.session.commit()
        increment_counter("link_finalized_success")

        return (
            jsonify(
                {
                    "status": "success",
                    "msg": "Manual link finalized. Lender now has access per policy.",
                    "subscriber_id": subscriber.id,
                }
            ),
            200,
        )

    except Exception as exc:
        db.session.rollback()
        _logger.exception("Manual link finalization failed: %s", exc)
        increment_counter("link_finalized_fail")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": "E_FINALIZE",
                        "message": "Failed to finalize link",
                    },
                }
            ),
            500,
        )


# =============================================================================
# 2B. LENDER SANDBOX MOCK DATA ENDPOINTS
# =============================================================================


@fintech_bp.route("/sandbox/account_snapshot", methods=["GET"])
@jwt_required()
@_rate_limit("60/hour")
def sandbox_account_snapshot():
    """
    Lender sandbox endpoint: Returns ONLY mock account metadata.

    Returns mock account metadata, balances, and analytics derived from
    mock transactions. Never touches real subscriber data.

    Query Parameters: None

    Response:
        {
            "status": "success",
            "data": {
                "account": {...},
                "balances": {...},
                "transactions": [...],
                "analytics": {...},
                "source": "sandbox_mock"
            }
        }
    """
    lender_user_id = get_jwt_identity()

    account_meta = MockDataService.generate_mock_account_metadata(lender_user_id)
    balance = MockDataService.generate_mock_balance()
    txns = MockDataService.generate_mock_transactions(days=30)
    analytics = MockDataService.generate_mock_analytics(txns)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "account": account_meta,
                    "balances": balance,
                    "transactions": txns,
                    "analytics": analytics,
                    "source": "sandbox_mock",
                },
            }
        ),
        200,
    )


@fintech_bp.route("/sandbox/statement/pdf", methods=["GET"])
@jwt_required()
@_rate_limit("20/hour")
def sandbox_statement_pdf():
    """
    Lender sandbox endpoint: Returns a base64-encoded mock PDF statement.

    Returns a base64-encoded mock PDF bank statement. Uses ONLY mock
    transactions and mock account metadata.

    Query Parameters: None

    Response:
        {
            "status": "success",
            "data": {
                "account": {...},
                "analytics": {...},
                "transaction_count": number,
                "statement_pdf_base64": "string",
                "source": "sandbox_mock"
            }
        }
    """
    lender_user_id = get_jwt_identity()

    result = MockDataService.generate_mock_statement_pdf(
        lender_user_id=lender_user_id,
        days=30,
        static_folder=current_app.static_folder,
    )

    pdf_b64 = base64.b64encode(result["pdf_bytes"]).decode("utf-8")

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "account": result["account"],
                    "analytics": result["analytics"],
                    "transaction_count": result["transaction_count"],
                    "statement_pdf_base64": pdf_b64,
                    "source": "sandbox_mock",
                },
            }
        ),
        200,
    )


# =============================================================================
# 3. TRANSACTION ROUTES
# =============================================================================

TRANSACTION_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "plaid_account_id": {"type": "string"},
        "account_id": {"type": "string"},
        "amount": {"type": "number"},
        "currency": {"type": "string"},
        "date": {"type": "string", "format": "date-time"},
        "name": {"type": "string"},
        "category": {"type": "string"},
    },
    "required": ["amount", "date", "name"],
    "additionalProperties": False,
}


@fintech_bp.route("/fintech/transactions", methods=["POST"])
@csrf.exempt
@jwt_required()
def create_transaction():
    """
    Create a new transaction with strict JSON validation and schema enforcement.

    Supports mock-mode for testing. Auto-fills missing date with current UTC time.
    Supports legacy 'description' field (maps to 'name').

    Request JSON:
        {
            "amount": number (required),
            "date": "ISO 8601 string" (required, auto-filled if missing),
            "name": "string" (required, or use 'description'),
            "currency": "string (optional, default: USD)",
            "category": "string (optional)",
            "account_id": "string (optional)",
            "plaid_account_id": "string (optional)"
        }

    Response (success):
        {
            "status": "success",
            "data": {
                "transaction_id": number,
                "amount": number,
                "name": "string",
                "date": "ISO 8601 string",
                "category": "string"
            }
        }
    """

    # -------------------------------------------------------------------------
    # 1. JSON VALIDATION (must run BEFORE schema + BEFORE auth logic)
    # -------------------------------------------------------------------------
    raw_data = request.get_json(silent=True)
    if not isinstance(raw_data, dict):
        return jsonify({"error": "Request must be JSON"}), 422

    # -------------------------------------------------------------------------
    # 2. Legacy compatibility: description → name
    # -------------------------------------------------------------------------
    if "description" in raw_data and "name" not in raw_data:
        raw_data["name"] = raw_data["description"]

    # -------------------------------------------------------------------------
    # 3. Auto-fill missing date
    # -------------------------------------------------------------------------
    if "date" not in raw_data or not raw_data["date"]:
        raw_data["date"] = datetime.utcnow().isoformat()

    # -------------------------------------------------------------------------
    # 4. Strip unknown fields
    # -------------------------------------------------------------------------
    allowed_fields = {
        "plaid_account_id",
        "account_id",
        "amount",
        "currency",
        "date",
        "name",
        "category",
    }
    data = {k: v for k, v in raw_data.items() if k in allowed_fields}

    # -------------------------------------------------------------------------
    # 5. Schema validation (AFTER JSON validation)
    # -------------------------------------------------------------------------
    try:
        validate_json_schema(TRANSACTION_CREATE_SCHEMA)(lambda: None)()
    except BadRequest as e:
        return jsonify({"error": str(e)}), 422

    # -------------------------------------------------------------------------
    # 6. Mock Mode (Testing)
    # -------------------------------------------------------------------------
    if current_app.config.get("TESTING", False):
        mock_id = f"MOCK_{uuid.uuid4().hex[:12]}"
        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "transaction_id": mock_id,
                        "amount": data.get("amount"),
                        "name": data.get("name"),
                        "date": data.get("date"),
                        "category": data.get("category"),
                    },
                }
            ),
            200,
        )

    # -------------------------------------------------------------------------
    # 7. Real transaction creation
    # -------------------------------------------------------------------------
    try:
        parsed_date = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))

        new_txn = Transaction(
            user_id=current_user.id,
            amount=data.get("amount"),
            date=parsed_date,
            name=data.get("name"),
            plaid_account_id=data.get("plaid_account_id"),
            account_id=data.get("account_id"),
            currency=data.get("currency", "USD"),
            category=data.get("category"),
        )

        db.session.add(new_txn)
        db.session.commit()

        _logger.info(
            "Transaction %s created for user %s",
            new_txn.id,
            current_user.id,
        )

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "transaction_id": new_txn.id,
                        "amount": new_txn.amount,
                        "name": new_txn.name,
                        "date": new_txn.date.isoformat(),
                        "category": new_txn.category,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        _logger.error(
            f"Transaction creation failed for {current_user.id}: {e}",
            exc_info=True,
        )
        return _envelope_error("Internal Server Error during transaction creation.", code=500)
