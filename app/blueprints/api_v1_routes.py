# =============================================================================
# FILE: app/blueprints/api_v1_routes.py
# DESCRIPTION: Version 1 of JWT-protected JSON endpoints (tightened/defensive)
# =============================================================================

import logging
import random
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Tuple

from dateutil.parser import parse
from flasgger import swag_from
from flask import Blueprint, Response, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
)
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException, Unauthorized
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import csrf, db
from app.models.schema_event import SchemaEvent
from app.models.tradeline import Tradeline
from app.models.user import User
from app.security.api_key_auth import require_api_key
from app.utils.api_response import error_response, success_response
from app.utils.rate_limit_guard import rate_limit_if_enabled
from app.utils.telemetry import increment_counter

logger = logging.getLogger(__name__)


# --- MFA PLACEHOLDER UTILS ---
def generate_mfa_secret(user_id: int) -> str:
    """Mock secret generation, in a real app this uses pyotp/qrcodes."""
    return f"MOCK_SECRET_{uuid4().hex[:16]}"


def verify_mfa_code(user_id: int, secret: str, code: str) -> bool:
    """Mock code verification."""
    return code == "123456"  # Simple mock success condition


# -------------------------------------------------------------------------
# Create a versioned blueprint (explicit prefix; keeps routes scoped)
api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


# =============================================================================
# Endpoints
# =============================================================================

@api_v1_bp.route("/core/transactions", methods=["POST"])
@csrf.exempt
def create_transaction():
    """Create a mock transaction (test harness endpoint)."""

    # 1. Check if the request is actually JSON
    if not request.is_json:
        return error_response(
            "E_JSON_REQUIRED",
            message="Request must be JSON",
            http_status_code=422,
        )

    # 2. Verify JWT (Confirmed working by test logs)
    from flask_jwt_extended import get_jwt, verify_jwt_in_request

    try:
        verify_jwt_in_request()
        logger.debug("JWT OK: %s", get_jwt())
    except Exception as e:
        logger.debug("JWT FAIL: %s %s", type(e).__name__, str(e))
        raise

    # 3. Parse JSON defensively
    data = request.get_json(silent=True) or {}

    # ⭐ SCHEMA VALIDATION GATE FIX
    required_fields = ("amount", "description", "account_id")
    if any(k not in data or data[k] is None or data[k] == "" for k in required_fields):
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing required fields: amount, description, account_id.",
            http_status_code=422,
        )

    # 4. If validation passes, return success with MOCK_ prefix
    tx_id = "MOCK_TX_123"
    return success_response({"transaction_id": tx_id})


# --- BLUEPRINT‑SCOPED ERROR HANDLERS ---
def handle_api_exception(
    exc: HTTPException, status_code: int, error_code: str, message: str
) -> Tuple[Response, int]:
    """Helper for logging and consistent error response format."""
    log_message = (
        f"API Error {status_code}: {getattr(exc, 'description', message)} Path: {request.path}"
    )
    logger.warning(log_message)
    try:
        increment_counter(f"http_error_{status_code}_v1")
    except Exception:
        logger.debug("increment_counter failed in error handler", exc_info=True)
    try:
        db.session.rollback()
    except Exception:
        logger.debug("db.session.rollback() failed in error handler", exc_info=True)
    return error_response(
        error_code,
        message=getattr(exc, "description", message),
        http_status_code=status_code,
        data={"error_type": exc.__class__.__name__},
    )


# Register BadRequest as blueprint-scoped so JSON parsing errors are remapped to 422
@api_v1_bp.errorhandler(BadRequest)
def bad_request_error(exc):
    return handle_api_exception(
        exc, 422, "E_VALIDATION", "Invalid data format or missing required fields."
    )


@api_v1_bp.errorhandler(401)
def unauthorized_error(exc):
    return handle_api_exception(exc, 401, "E_UNAUTHORIZED", "Authentication required.")


@api_v1_bp.errorhandler(403)
def forbidden_error(exc):
    return handle_api_exception(exc, 403, "E_FORBIDDEN", "Permission denied.")


@api_v1_bp.errorhandler(404)
def not_found_error(exc):
    """
    Defensive safety: if the request path does not start with this blueprint's
    url_prefix, re-raise the exception so another blueprint or the global handler
    can respond. This prevents api_v1_bp's 404 handler from swallowing routes
    clearly outside /api/v1 when registration order is wrong.
    """
    try:
        bp_prefix = api_v1_bp.url_prefix or ""
        # Normalize trailing slash for comparison
        prefix_normalized = bp_prefix.rstrip("/") or "/"
        if not request.path.startswith(prefix_normalized):
            # Let higher-level handlers own this 404 (re-raise)
            raise exc
    except Exception:
        # If anything goes wrong in the guard, re-raise to avoid silent interception.
        raise exc

    return handle_api_exception(exc, 404, "E_NOT_FOUND", "The requested resource was not found.")


@api_v1_bp.errorhandler(422)
def validation_error(exc):
    return handle_api_exception(
        exc, 422, "E_VALIDATION", "Invalid data format or missing required fields."
    )


@api_v1_bp.errorhandler(500)
def internal_server_error(exc):
    log_message = (
        "SERVER ERROR 500: "
        f"{getattr(exc, 'description', 'Unhandled Server Error')} "
        f"Path: {request.path}"
    )
    logger.error(log_message, exc_info=True)
    try:
        increment_counter("http_error_500_v1")
    except Exception:
        logger.debug("increment_counter failed in 500 handler", exc_info=True)
    try:
        db.session.rollback()
    except Exception:
        logger.debug("db.session.rollback() failed in 500 handler", exc_info=True)
    return handle_api_exception(exc, 500, "E_SERVER_ERROR", "An unexpected server error occurred.")


# --- PUBLIC UTILITY ENDPOINTS ---
@api_v1_bp.route("/ping", methods=["GET"])
@csrf.exempt
@swag_from(
    {
        "tags": ["Public"],
        "responses": {200: {"description": "A simple heartbeat response."}},
    }
)
def ping():
    """V1 Health Check (Ping)"""
    return success_response({"status": "healthy"}, message="Pong!")


@api_v1_bp.route("/health", methods=["GET"])
@csrf.exempt
@swag_from(
    {
        "tags": ["Public"],
        "responses": {200: {"description": "Detailed application health status."}},
    }
)
def api_health():
    """Detailed V1 Health Status"""
    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_status = "error"
        logger.error("Health check failed: Database connection error.", exc_info=True)
        try:
            increment_counter("health_check_db_failure_v1")
        except Exception:
            logger.debug("increment_counter failed in health check", exc_info=True)

    # ⭐ UTC DEPRECATION FIX
    return success_response(
        {
            "status": "ok",
            "database": db_status,
            "current_time": datetime.now(timezone.utc).isoformat(),
        },
        http_status_code=(200 if db_status == "ok" else 503),
    )


@api_v1_bp.route("/public/stats", methods=["GET"])
@rate_limit_if_enabled("100/hour")
@csrf.exempt
@require_api_key()
@swag_from(
    {
        "tags": ["Public"],
        "security": [{"APIKeyAuth": []}],
        "responses": {
            "200": {"description": "Public system statistics (API Key Required)."},
            "401": {"description": "Missing or invalid API Key."},
        },
    }
)
def public_stats():
    """Public System Statistics (API Key required)"""
    stats = {
        "user_count": User.query.count(),
        "tradeline_count": Tradeline.query.count(),
        "api_calls_today": random.randint(1000, 5000),
        "api_version": "v1.0",
    }
    return success_response(stats, message="Public API usage statistics.")


# --- AUTH ENDPOINTS ---
@api_v1_bp.route("/auth/register", methods=["POST"])
@rate_limit_if_enabled("5/hour")
@csrf.exempt
@swag_from({
    "tags": ["Auth"],
    "summary": "Register a new user (with stricter validation).",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["email", "password", "username"],
                "properties": {
                    "email": {"type": "string", "description": "User email."},
                    "password": {"type": "string", "description": "User password (min 8 chars)."},
                    "username": {"type": "string", "description": "User chosen username."}
                }
            }
        }
    ],
    "responses": {
        "200": {"description": "Registration successful."},
        "422": {"description": "Validation Error."}
    }
})
def register():
    """Register a new user (with stricter validation)."""
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")
    username = data.get("username")

    if not all([email, password, username]):
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing email, password, or username.",
            http_status_code=422,
        )

    if len(password) < 8:
        return error_response(
            "E_PASSWORD_WEAK",
            message="Password must be at least 8 characters.",
            http_status_code=422,
        )

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return error_response(
            "E_EMAIL_INVALID", message="Invalid email format.", http_status_code=422
        )

    if User.query.filter_by(email=email).first():
        return error_response(
            "E_EMAIL_EXISTS",
            message="Email address already registered.",
            http_status_code=422,
        )

    if User.query.filter_by(username=username).first():
        return error_response(
            "E_USERNAME_EXISTS", message="Username already taken.", http_status_code=422
        )

    try:
        new_user = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            is_approved=True,
            is_mfa_enabled=False,
        )
        db.session.add(new_user)

        # Flush the session to generate the new_user.id before using it in the SchemaEvent
        db.session.flush()

        db.session.add(
            SchemaEvent(
                user_id=new_user.id,
                event_type="USER_REGISTERED_V1",
                origin=f"user:{new_user.id}",
                detail=f"New user registered: {new_user.email}",
            )
        )
        db.session.commit()

        try:
            increment_counter("auth_register_success_v1")
        except Exception:
            logger.debug("increment_counter failed after registration", exc_info=True)

        return success_response(
            {
                "user_id": new_user.id,
                "username": new_user.username,
                "message": "Registration successful. You can now log in.",
            }
        )

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(f"DB Error on registration: {exc}", exc_info=True)
        return error_response(
            "E_DB_ERROR",
            message="A database error occurred during registration.",
            http_status_code=500,
        )


@api_v1_bp.route("/auth/login", methods=["POST"])
@rate_limit_if_enabled("10/minute")
@csrf.exempt
@swag_from(
    {
        "tags": ["Auth"],
        "responses": {
            200: {"description": "Login successful, returns access and refresh tokens."},
            401: {"description": "Invalid credentials or user not approved."},
        },
    }
)
def login():
    """User login and JWT token issuance (with approval + MFA + audit hardening)."""
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    # Basic payload validation
    if not email or not password:
        increment_counter("auth_login_fail_missing_fields_v1")
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing email or password.",
            http_status_code=422,
        )

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        increment_counter("auth_login_fail_credentials_v1")
        return error_response(
            "E_INVALID_CREDENTIALS",
            message="Invalid email or password.",
            http_status_code=401,
        )

    # --- Auth Hardening: Check Approval Status ---
    if not user.is_approved:
        increment_counter("auth_login_fail_not_approved_v1")
        return error_response(
            "E_NOT_APPROVED",
            message="Account is pending approval.",
            http_status_code=403,
        )

    # Capture request metadata for audit
    ip_address = request.remote_addr
    user_agent = request.headers.get("User-Agent", "")

    # Check if MFA is required
    if user.is_mfa_enabled and not data.get("mfa_code"):
        increment_counter("auth_login_fail_mfa_required_v1")
        return error_response(
            "E_MFA_REQUIRED",
            message="MFA code is required for login.",
            http_status_code=401,
            data={"mfa_required": True},
        )

    if user.is_mfa_enabled:
        mfa_code = (data.get("mfa_code") or "").strip()
        if not verify_mfa_code(user.id, user.mfa_secret, mfa_code):
            increment_counter("auth_login_fail_mfa_v1")
            return error_response(
                "E_MFA_INVALID",
                message="Invalid MFA code.",
                http_status_code=401,
            )

    access_token = create_access_token(
        identity=user.id,
        expires_delta=timedelta(hours=1),
    )

    # ⭐ REFRESH TOKEN FIX
    refresh_token = create_refresh_token(identity=user.id)

    try:
        db.session.flush()
        # ⭐ UTC DEPRECATION FIX
        user.last_login_at = datetime.now(timezone.utc)

        audit_event = SchemaEvent(
            user_id=user.id,
            event_type="TOKEN_ISSUE",
            origin=f"user:{user.id}",
            detail=f"JWT issued for user login from IP={ip_address}, UA={user_agent}",
        )

        db.session.add(audit_event)
        db.session.commit()

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(
            f"DB Error logging TOKEN_ISSUE for user {getattr(user, 'id', None)}: {exc}",
            exc_info=True
        )

    increment_counter("auth_login_success_v1")

    response = success_response(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_id": user.id,
            "is_mfa_enabled": user.is_mfa_enabled,
        },
        message="Login successful.",
    )

    set_access_cookies(response, access_token)

    return response


@api_v1_bp.route("/auth/token/refresh", methods=["POST"])
@jwt_required(refresh=True)
@rate_limit_if_enabled("5/hour")
@csrf.exempt
@swag_from({"tags": ["Auth"], "responses": {200: {"description": "New access token granted."}}})
def refresh_token():
    """Refreshes the JWT access token."""
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(
        identity=current_user_id, expires_delta=timedelta(hours=1)
    )

    response = success_response(
        {"access_token": new_access_token}, message="Token refreshed successfully."
    )
    set_access_cookies(response, new_access_token)

    return response


# --- MFA Endpoints ---
@api_v1_bp.route("/auth/mfa/verify", methods=["POST"])
@jwt_required()
@rate_limit_if_enabled("5/hour")
@swag_from({
    "tags": ["Auth"],
    "summary": "Verifies the MFA code and enables MFA for the user.",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["mfa_code"],
                "properties": {
                    "mfa_code": {"type": "string", "description": "Code from authenticator app."}
                }
            }
        }
    ],
    "responses": {
        "200": {"description": "MFA verification successful."},
        "401": {"description": "Invalid MFA code."}
    }
})
def mfa_verify():
    """Verifies the MFA code and enables MFA for the user."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    mfa_code = data.get("mfa_code")

    user = User.query.get(user_id)

    if not user:
        raise Unauthorized("User not found.")

    if not mfa_code:
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing MFA code.",
            http_status_code=422,
        )

    if not user.mfa_secret:
        return error_response(
            "E_MFA_NOT_SETUP",
            message="MFA setup has not been initiated for this account.",
            http_status_code=400,
        )

    if verify_mfa_code(user.id, user.mfa_secret, mfa_code):
        try:
            user.is_mfa_enabled = True

            db.session.add(
                SchemaEvent(
                    event_type="MFA_SETUP_COMPLETE_V1",
                    origin=f"user:{user.id}",
                    detail="MFA successfully enabled.",
                )
            )
            db.session.commit()

            increment_counter("auth_mfa_setup_success_v1")
            return success_response(
                {"is_mfa_enabled": True},
                message="MFA successfully enabled and verified.",
            )

        except SQLAlchemyError as exc:
            db.session.rollback()
            logger.error(
                f"DB Error during MFA verification for user {user.id}: {exc}",
                exc_info=True
            )
            return error_response(
                "E_DB_ERROR",
                message="A database error occurred during MFA verification.",
                http_status_code=500,
            )

    increment_counter("auth_mfa_setup_fail_v1")
    return error_response(
        "E_MFA_INVALID",
        message="Invalid MFA code. Please check your authenticator app and try again.",
        http_status_code=401,
    )



# --- TRADELINE CRUD ENDPOINTS ---
@api_v1_bp.route("/tradelines", methods=["GET"])
@jwt_required()
@rate_limit_if_enabled("60/minute")
@swag_from(
    {
        "tags": ["Tradelines"],
        "parameters": [
            {
                "name": "limit",
                "in": "query",
                "type": "integer",
                "default": 10,
                "description": "Number of records to return (max 100).",
            },
            {
                "name": "offset",
                "in": "query",
                "type": "integer",
                "default": 0,
                "description": "Number of records to skip.",
            },
        ],
        "responses": {200: {"description": "List of tradelines."}},
    }
)
def list_tradelines():
    """List all tradelines for the authenticated user (Standardized to limit/offset)."""
    user_id = get_jwt_identity()

    try:
        # ⭐ PAGINATION EXCEPTION HANDLING FIX
        try:
            limit = min(max(int(request.args.get("limit", 10)), 1), 100)
            offset = max(int(request.args.get("offset", 0)), 0)
        except ValueError:
            return error_response(
                "E_INVALID_PAGINATION",
                message="Query parameters 'limit' and 'offset' must be valid integers.",
                http_status_code=422,
            )

        query = Tradeline.query.filter_by(user_id=user_id).order_by(Tradeline.date_opened.desc())

        total_count = query.count()
        tradelines = query.limit(limit).offset(offset).all()

        tradeline_data = [t.to_dict() for t in tradelines]

        return success_response(
            {
                "tradelines": tradeline_data,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_records": total_count,
                },
            },
            message=f"Fetched {len(tradeline_data)} tradelines.",
        )

    except Exception as exc:
        logger.error(f"Error fetching tradelines for user {user_id}: {exc}", exc_info=True)
        return error_response(
            "E_FETCH_ERROR", message="Could not fetch tradelines.", http_status_code=500
        )


@api_v1_bp.route("/tradelines", methods=["POST"])
@jwt_required()
@rate_limit_if_enabled("30/minute")
@csrf.exempt
@swag_from(
    {
        "tags": ["Tradelines"],
        "responses": {
            200: {"description": "Tradeline created."},
            422: {"description": "Validation error."},
        },
    }
)
def create_tradeline():
    """Creates a new tradeline for the authenticated user."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    if not all(k in data for k in ["account_number", "balance", "date_opened"]):
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing required fields: account_number, balance, date_opened.",
            http_status_code=422,
        )

    try:
        new_tradeline = Tradeline(
            user_id=user_id,
            account_number=data["account_number"],
            balance=data["balance"],
            date_opened=parse(data["date_opened"]),
            creditor_name=data.get("creditor_name"),
        )
        db.session.add(new_tradeline)

        db.session.add(
            SchemaEvent(
                event_type="TRADELINE_CREATE_V1",
                origin=f"user:{user_id}",
                detail=f"Tradeline created: {new_tradeline.account_number}",
            )
        )

        db.session.commit()
        increment_counter("api_tradeline_create_success_v1")

        return success_response(
            new_tradeline.to_dict(),
            message="Tradeline created successfully.",
            http_status_code=201,
        )

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(f"DB Error on tradeline creation: {exc}", exc_info=True)
        return error_response(
            "E_DB_ERROR", message="A database error occurred.", http_status_code=500
        )
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Error processing tradeline data: {exc}", exc_info=True)
        return error_response("E_DATA_PARSE", message="Invalid data format.", http_status_code=422)


@api_v1_bp.route("/tradelines/<int:tradeline_id>", methods=["GET"])
@jwt_required()
@rate_limit_if_enabled("60/minute")
@swag_from(
    {
        "tags": ["Tradelines"],
        "responses": {
            200: {"description": "Single tradeline details."},
            404: {"description": "Not found."},
        },
    }
)
def get_tradeline(tradeline_id):
    """Retrieves a single tradeline by ID with ownership check."""
    user_id = get_jwt_identity()
    tradeline = Tradeline.query.filter_by(id=tradeline_id, user_id=user_id).first()

    if not tradeline:
        increment_counter("api_tradeline_get_not_found_v1")
        return error_response(
            "E_NOT_FOUND",
            message=f"Tradeline with ID {tradeline_id} not found or access denied.",
            http_status_code=404,
        )

    return success_response(tradeline.to_dict())


@api_v1_bp.route("/tradelines/<int:tradeline_id>", methods=["PUT"])
@jwt_required()
@rate_limit_if_enabled("30/minute")
@csrf.exempt
@swag_from(
    {
        "tags": ["Tradelines"],
        "responses": {
            200: {"description": "Tradeline updated."},
            404: {"description": "Not found."},
        },
    }
)
def update_tradeline(tradeline_id):
    """Updates an existing tradeline with ownership check."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    tradeline = Tradeline.query.filter_by(id=tradeline_id, user_id=user_id).first()

    if not tradeline:
        increment_counter("api_tradeline_update_not_found_v1")
        return error_response(
            "E_NOT_FOUND",
            message=f"Tradeline with ID {tradeline_id} not found or access denied.",
            http_status_code=404,
        )

    try:
        if "balance" in data:
            tradeline.balance = data["balance"]
        if "creditor_name" in data:
            tradeline.creditor_name = data["creditor_name"]

        db.session.add(
            SchemaEvent(
                event_type="TRADELINE_UPDATE_V1",
                origin=f"user:{user_id}",
                detail=(
                    f"Tradeline {tradeline_id} updated: Balance="
                    f"{data.get('balance', tradeline.balance)}"
                ),
            )
        )

        db.session.commit()
        increment_counter("api_tradeline_update_success_v1")

        return success_response(
            tradeline.to_dict(),
            message=f"Tradeline {tradeline_id} updated successfully.",
        )

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(f"DB Error on tradeline update: {exc}", exc_info=True)
        return error_response(
            "E_DB_ERROR",
            message="A database error occurred during the update.",
            http_status_code=500,
        )
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Error processing tradeline data: {exc}", exc_info=True)
        return error_response("E_DATA_PARSE", message="Invalid data format.", http_status_code=422)


@api_v1_bp.route("/tradelines/<int:tradeline_id>", methods=["DELETE"])
@jwt_required()
@rate_limit_if_enabled("10/minute")
@csrf.exempt
@swag_from(
    {
        "tags": ["Tradelines"],
        "responses": {
            200: {"description": "Tradeline deleted."},
            404: {"description": "Not found."},
        },
    }
)
def delete_tradeline(tradeline_id):
    """Deletes a specific tradeline with ownership check."""
    user_id = get_jwt_identity()
    tradeline = Tradeline.query.filter_by(id=tradeline_id, user_id=user_id).first()

    if not tradeline:
        increment_counter("api_tradeline_delete_not_found_v1")
        return error_response(
            "E_NOT_FOUND",
            message=f"Tradeline with ID {tradeline_id} not found or access denied.",
            http_status_code=404,
        )

    try:
        db.session.add(
            SchemaEvent(
                event_type="TRADELINE_DELETE_V1",
                origin=f"user:{user_id}",
                detail=f"Tradeline {tradeline_id} deleted: {tradeline.account_number}",
            )
        )

        db.session.delete(tradeline)
        db.session.commit()

        increment_counter("api_tradeline_delete_success_v1")
        return success_response(
            {"tradeline_id": tradeline_id},
            message=f"Tradeline {tradeline_id} deleted successfully.",
        )

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(f"DB Error on tradeline deletion: {exc}", exc_info=True)
        return error_response(
            "E_DB_ERROR",
            message="A database error occurred during deletion.",
            http_status_code=500,
        )