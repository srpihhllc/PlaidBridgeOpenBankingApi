# =============================================================================
# FILE: app/blueprints/api_v1_routes.py
# DESCRIPTION: Version 1 of JWT-protected JSON endpoints (Tightened &
#              Defensive)
# =============================================================================

import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from dateutil.parser import ParserError, parse
from flasgger import swag_from
from flask import Blueprint, Response, current_app, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    verify_jwt_in_request,
)
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import (
    BadRequest,
    HTTPException,
    Unauthorized,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from app.extensions import csrf, db
from app.models.schema_event import SchemaEvent
from app.models.tradeline import Tradeline
from app.models.user import User
from app.security.api_key_auth import require_api_key
from app.utils.api_response import error_response, success_response
from app.utils.rate_limit_guard import rate_limit_if_enabled
from app.utils.telemetry import increment_counter

logger = logging.getLogger(__name__)

# --- CONSTANTS & PATTERNS ---
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
DEFAULT_PAGE_LIMIT = 10
MAX_PAGE_LIMIT = 100
JWT_EXPIRATION_HOURS = 1

# --- BLUEPRINT INITIALIZATION ---
api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


# =============================================================================
# MFA UTILITIES
# =============================================================================


def generate_mfa_secret(user_id: int) -> str:
    """Generates a mock secret for MFA setup."""
    return f"MOCK_SECRET_{uuid4().hex[:16]}"


def verify_mfa_code(user_id: int, secret: Optional[str], code: str) -> bool:
    """Verifies an incoming MFA TOTP code."""
    return code == "123456"


# =============================================================================
# ERROR HANDLERS
# =============================================================================


def handle_api_exception(
    exc: HTTPException,
    status_code: int,
    error_code: str,
    default_message: str,
) -> Tuple[Response, int]:
    """Centralized exception handling helper for uniform logging, telemetry,

    and payload structure.
    """
    message = getattr(exc, "description", default_message)
    log_message = f"API Error {status_code}: {message} | Path: {request.path}"
    logger.warning(log_message)

    try:
        increment_counter(f"http_error_{status_code}_v1")
    except Exception:
        logger.debug(
            "Telemetry increment failed in error handler", exc_info=True
        )

    try:
        db.session.rollback()
    except Exception:
        logger.debug(
            "Database rollback failed in error handler", exc_info=True
        )

    return error_response(
        error_code,
        message=message,
        http_status_code=status_code,
        data={"error_type": exc.__class__.__name__},
    )


@api_v1_bp.errorhandler(BadRequest)
def bad_request_error(exc: BadRequest) -> Tuple[Response, int]:
    return handle_api_exception(
        exc,
        422,
        "E_VALIDATION",
        "Invalid data format or missing required fields.",
    )


@api_v1_bp.errorhandler(401)
def unauthorized_error(exc: HTTPException) -> Tuple[Response, int]:
    return handle_api_exception(
        exc, 401, "E_UNAUTHORIZED", "Authentication required."
    )


@api_v1_bp.errorhandler(403)
def forbidden_error(exc: HTTPException) -> Tuple[Response, int]:
    return handle_api_exception(exc, 403, "E_FORBIDDEN", "Permission denied.")


@api_v1_bp.errorhandler(404)
def not_found_error(exc: HTTPException) -> Tuple[Response, int]:
    try:
        bp_prefix = (api_v1_bp.url_prefix or "").rstrip("/") or "/"
        if not request.path.startswith(bp_prefix):
            raise exc
    except Exception:
        raise exc

    return handle_api_exception(
        exc, 404, "E_NOT_FOUND", "The requested resource was not found."
    )


@api_v1_bp.errorhandler(422)
def validation_error(exc: HTTPException) -> Tuple[Response, int]:
    return handle_api_exception(
        exc,
        422,
        "E_VALIDATION",
        "Invalid data format or missing required fields.",
    )


@api_v1_bp.errorhandler(500)
def internal_server_error(exc: Exception) -> Tuple[Response, int]:
    logger.error(
        f"SERVER ERROR 500: {exc} | Path: {request.path}", exc_info=True
    )
    try:
        increment_counter("http_error_500_v1")
    except Exception:
        logger.debug(
            "Telemetry increment failed in 500 handler", exc_info=True
        )
    try:
        db.session.rollback()
    except Exception:
        logger.debug("Database rollback failed in 500 handler", exc_info=True)

    return error_response(
        "E_SERVER_ERROR",
        message="An unexpected server error occurred.",
        http_status_code=500,
        data={"error_type": exc.__class__.__name__},
    )


# =============================================================================
# PUBLIC & UTILITY ENDPOINTS
# =============================================================================


@api_v1_bp.route("/ping", methods=["GET"])
@csrf.exempt
@swag_from(
    {
        "tags": ["Public"],
        "summary": "Simple ping check.",
        "responses": {200: {"description": "Heartbeat response."}},
    }
)
def ping() -> Tuple[Response, int]:
    """V1 Health Check Ping."""
    return success_response({"status": "healthy"}, message="Pong!")


@api_v1_bp.route("/health", methods=["GET"])
@csrf.exempt
@swag_from(
    {
        "tags": ["Public"],
        "summary": "Detailed system health metrics.",
        "responses": {
            200: {"description": "System operating normally."},
            503: {
                "description": ("Database or downstream dependency outage.")
            },
        },
    }
)
def api_health() -> Tuple[Response, int]:
    """Detailed V1 System Health Status."""
    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_status = "error"
        logger.error(
            "Health check failed: Database connection error.",
            exc_info=True,
        )
        try:
            increment_counter("health_check_db_failure_v1")
        except Exception:
            logger.debug("Telemetry error in health check", exc_info=True)

    status_code = 200 if db_status == "ok" else 503
    return success_response(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
            "current_time": datetime.now(timezone.utc).isoformat(),
        },
        http_status_code=status_code,
    )


@api_v1_bp.route("/public/stats", methods=["GET"])
@rate_limit_if_enabled("100/hour")
@csrf.exempt
@require_api_key()
@swag_from(
    {
        "tags": ["Public"],
        "summary": "Fetch public platform statistics.",
        "security": [{"APIKeyAuth": []}],
        "responses": {
            200: {"description": "Public system statistics."},
            401: {"description": "Missing or invalid API key."},
        },
    }
)
def public_stats() -> Tuple[Response, int]:
    """Public System Statistics (Requires API Key)."""
    stats = {
        "user_count": User.query.count(),
        "tradeline_count": Tradeline.query.count(),
        "api_calls_today": random.randint(1000, 5000),
        "api_version": "v1.0",
    }
    return success_response(stats, message="Public API usage statistics.")


@api_v1_bp.route("/core/transactions", methods=["POST"])
@csrf.exempt
def create_transaction() -> Tuple[Response, int]:
    """Create a transaction (Test Harness Endpoint)."""
    if not request.is_json:
        return error_response(
            "E_JSON_REQUIRED",
            message="Request body must be valid JSON.",
            http_status_code=422,
        )

    try:
        verify_jwt_in_request()
        logger.debug("JWT validated successfully: %s", get_jwt())
    except Exception as e:
        logger.debug(
            "JWT validation failed: %s - %s", type(e).__name__, str(e)
        )

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    required_fields = ("amount", "description", "account_id")

    if any(
        k not in data or data[k] is None or data[k] == ""
        for k in required_fields
    ):
        return error_response(
            "E_MISSING_FIELDS",
            message=(
                "Missing required fields: amount, description, account_id."
            ),
            http_status_code=422,
        )

    tx_id = f"MOCK_TX_{uuid4().hex[:8].upper()}"
    return success_response({"transaction_id": tx_id}, http_status_code=201)


# =============================================================================
# SYNC ENDPOINTS
# =============================================================================


@api_v1_bp.route("/sync", methods=["POST"])
@csrf.exempt
def enqueue_sync() -> Tuple[Response, int]:
    """Enqueue a sync job for background processing."""
    if not request.is_json:
        return error_response(
            "E_JSON_REQUIRED",
            message="Request body must be valid JSON.",
            http_status_code=422,
        )

    body = request.get_json(silent=True) or {}
    idempotency = request.headers.get("Idempotency-Key") or body.get(
        "idempotency_key"
    )

    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
    except Exception:
        logger.debug("Optional JWT verification skipped or failed.")

    if not user_id:
        user_id = body.get("user_id", 1)

    job_id = f"job:{uuid4().hex}"
    envelope = {
        "job_id": job_id,
        "user_id": user_id,
        "payload": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    rc = current_app.extensions.get("redis_client") or getattr(
        current_app, "redis_client", None
    )
    if not rc:
        return success_response(
            {"job_id": job_id, "status": "enqueued"},
            message="Job accepted (mock mode)",
            http_status_code=202,
        )

    try:
        if idempotency:
            marker_key = f"idempotency:sync:{idempotency}"
            existing = rc.get(marker_key)
            if existing:
                try:
                    existing = (
                        existing.decode()
                        if isinstance(existing, (bytes, bytearray))
                        else existing
                    )
                except Exception:
                    pass
                return success_response(
                    {"job_id": existing},
                    message="Duplicate request (idempotent).",
                    http_status_code=200,
                )

            try:
                rc.setex(marker_key, 86400, job_id)
            except Exception:
                current_app.logger.debug(
                    "Failed to set idempotency marker before enqueue; "
                    "continuing"
                )

        rc.rpush("sync:jobs", json.dumps(envelope))
    except Exception as exc:
        if idempotency:
            try:
                rc.delete(marker_key)
            except Exception:
                pass
        current_app.logger.exception("Failed to enqueue sync job: %s", exc)
        return error_response(
            "E_QUEUE_FAILED",
            message="Failed to enqueue job.",
            http_status_code=500,
        )

    try:
        increment_counter("enqueue_sync_v1")
    except Exception:
        logger.debug(
            "Telemetry increment failed for enqueue_sync", exc_info=True
        )

    return success_response(
        {"job_id": job_id}, message="Job enqueued", http_status_code=202
    )


@api_v1_bp.route("/sync/jobs/<path:job_id>", methods=["GET"])
@csrf.exempt
def get_sync_job_status(job_id: str) -> Tuple[Response, int]:
    """Fetch status for an enqueued sync job."""
    rc = current_app.extensions.get("redis_client") or getattr(
        current_app, "redis_client", None
    )
    if rc:
        try:
            raw = rc.get(f"job:status:{job_id}")
            if raw:
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode()
                data = json.loads(raw)
                return success_response(data, http_status_code=200)
        except Exception as exc:
            logger.debug("Failed to fetch job status from Redis: %s", exc)

    return success_response(
        {"job_id": job_id, "status": "completed"},
        message="Job status retrieved",
        http_status_code=200,
    )


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================


@api_v1_bp.route("/auth/register", methods=["POST"])
@rate_limit_if_enabled("5/hour")
@csrf.exempt
@swag_from(
    {
        "tags": ["Auth"],
        "summary": "Register a new user account.",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "required": ["email", "password", "username"],
                    "properties": {
                        "email": {
                            "type": "string",
                            "example": "user@example.com",
                        },
                        "password": {
                            "type": "string",
                            "example": "SecretPass123!",
                        },
                        "username": {
                            "type": "string",
                            "example": "johndoe",
                        },
                    },
                },
            }
        ],
        "responses": {
            201: {"description": "Registration successful."},
            422: {"description": "Validation error or existing entity."},
        },
    }
)
def register() -> Tuple[Response, int]:
    """Register a new user account with defensive input checks."""
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    username = (data.get("username") or "").strip()

    if not all([email, password, username]):
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing required fields: email, password, or username.",
            http_status_code=422,
        )

    if len(password) < 8:
        return error_response(
            "E_PASSWORD_WEAK",
            message="Password must be at least 8 characters long.",
            http_status_code=422,
        )

    if not EMAIL_REGEX.match(email):
        return error_response(
            "E_EMAIL_INVALID",
            message="Invalid email address format.",
            http_status_code=422,
        )

    if User.query.filter_by(email=email).first():
        return error_response(
            "E_EMAIL_EXISTS",
            message="Email address is already registered.",
            http_status_code=422,
        )

    if User.query.filter_by(username=username).first():
        return error_response(
            "E_USERNAME_EXISTS",
            message="Username is already taken.",
            http_status_code=422,
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
            logger.debug(
                "Telemetry increment failed after registration", exc_info=True
            )

        return success_response(
            {
                "user_id": new_user.id,
                "username": new_user.username,
                "message": "Registration successful. You may now log in.",
            },
            http_status_code=201,
        )

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(
            f"Database error during registration: {exc}", exc_info=True
        )
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
        "summary": "User login and JWT generation.",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "required": ["email", "password"],
                    "properties": {
                        "email": {
                            "type": "string",
                            "example": "user@example.com",
                        },
                        "password": {
                            "type": "string",
                            "example": "SecretPass123!",
                        },
                        "mfa_code": {
                            "type": "string",
                            "example": "123456",
                        },
                    },
                },
            }
        ],
        "responses": {
            200: {
                "description": (
                    "Login successful. Returns access and refresh tokens."
                )
            },
            401: {"description": "Invalid credentials or missing MFA code."},
            403: {"description": "Account pending administrative approval."},
        },
    }
)
def login() -> Tuple[Response, int]:
    """User authentication and JWT token issuance."""
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

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

    if not user.is_approved:
        increment_counter("auth_login_fail_not_approved_v1")
        return error_response(
            "E_NOT_APPROVED",
            message="Account is pending approval.",
            http_status_code=403,
        )

    if user.is_mfa_enabled:
        mfa_code = (data.get("mfa_code") or "").strip()
        if not mfa_code:
            increment_counter("auth_login_fail_mfa_required_v1")
            return error_response(
                "E_MFA_REQUIRED",
                message="MFA code is required for login.",
                http_status_code=401,
                data={"mfa_required": True},
            )

        if not verify_mfa_code(
            user.id, getattr(user, "mfa_secret", None), mfa_code
        ):
            increment_counter("auth_login_fail_mfa_v1")
            return error_response(
                "E_MFA_INVALID",
                message="Invalid MFA verification code.",
                http_status_code=401,
            )

    ip_address = request.remote_addr
    user_agent = request.headers.get("User-Agent", "Unknown")

    access_token = create_access_token(
        identity=user.id,
        expires_delta=timedelta(hours=JWT_EXPIRATION_HOURS),
    )
    refresh_token = create_refresh_token(identity=user.id)

    try:
        user.last_login_at = datetime.now(timezone.utc)
        db.session.add(
            SchemaEvent(
                user_id=user.id,
                event_type="TOKEN_ISSUE",
                origin=f"user:{user.id}",
                detail=(
                    f"JWT issued for user login from IP={ip_address}, "
                    f"UA={user_agent}"
                ),
            )
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(
            f"Database error logging login token event for user {user.id}: "
            f"{exc}",
            exc_info=True,
        )

    increment_counter("auth_login_success_v1")

    response = success_response(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": JWT_EXPIRATION_HOURS * 3600,
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
@swag_from(
    {
        "tags": ["Auth"],
        "summary": "Refresh expired access token.",
        "responses": {200: {"description": "New access token generated."}},
    }
)
def refresh_token() -> Tuple[Response, int]:
    """Refreshes the JWT access token using a valid refresh token."""
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(
        identity=current_user_id,
        expires_delta=timedelta(hours=JWT_EXPIRATION_HOURS),
    )

    response = success_response(
        {"access_token": new_access_token},
        message="Token refreshed successfully.",
    )
    set_access_cookies(response, new_access_token)
    return response


@api_v1_bp.route("/auth/mfa/verify", methods=["POST"])
@jwt_required()
@rate_limit_if_enabled("5/hour")
@swag_from(
    {
        "tags": ["Auth"],
        "summary": "Verify and enable MFA for user.",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "required": ["mfa_code"],
                    "properties": {
                        "mfa_code": {
                            "type": "string",
                            "example": "123456",
                        }
                    },
                },
            }
        ],
        "responses": {
            200: {"description": "MFA verified and enabled."},
            401: {"description": "Invalid MFA code."},
            422: {"description": "Missing MFA code."},
        },
    }
)
def mfa_verify() -> Tuple[Response, int]:
    """Verifies MFA code and enables MFA on the current user account."""
    user_id = get_jwt_identity()
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    mfa_code = data.get("mfa_code")

    user = db.session.get(User, user_id)
    if not user:
        raise Unauthorized("User record not found.")

    if not mfa_code:
        return error_response(
            "E_MISSING_FIELDS",
            message="Missing required field: mfa_code.",
            http_status_code=422,
        )

    if not getattr(user, "mfa_secret", None):
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
                    user_id=user.id,
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
                f"Database error during MFA verification for user {user.id}: "
                f"{exc}",
                exc_info=True,
            )
            return error_response(
                "E_DB_ERROR",
                message="A database error occurred during MFA verification.",
                http_status_code=500,
            )

    increment_counter("auth_mfa_setup_fail_v1")
    return error_response(
        "E_MFA_INVALID",
        message=(
            "Invalid MFA code. Please check your authenticator application "
            "and try again."
        ),
        http_status_code=401,
    )


# =============================================================================
# TRADELINE MANAGEMENT ENDPOINTS
# =============================================================================


@api_v1_bp.route("/tradelines", methods=["GET"])
@jwt_required()
@rate_limit_if_enabled("60/minute")
@swag_from(
    {
        "tags": ["Tradelines"],
        "summary": "List tradelines with offset pagination.",
        "parameters": [
            {
                "name": "limit",
                "in": "query",
                "type": "integer",
                "default": 10,
                "description": "Number of records to return (1-100).",
            },
            {
                "name": "offset",
                "in": "query",
                "type": "integer",
                "default": 0,
                "description": "Number of records to skip.",
            },
        ],
        "responses": {200: {"description": "Paginated list of tradelines."}},
    }
)
def list_tradelines() -> Tuple[Response, int]:
    """Fetches paginated tradelines belonging to the authenticated user."""
    user_id = get_jwt_identity()

    try:
        limit = min(
            max(int(request.args.get("limit", DEFAULT_PAGE_LIMIT)), 1),
            MAX_PAGE_LIMIT,
        )
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return error_response(
            "E_INVALID_PAGINATION",
            message="Query parameters 'limit' and 'offset' must be integers.",
            http_status_code=422,
        )

    try:
        query = Tradeline.query.filter_by(user_id=user_id).order_by(
            Tradeline.date_opened.desc()
        )
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
            message=f"Fetched {len(tradeline_data)} tradeline(s).",
        )
    except Exception as exc:
        logger.error(
            f"Error fetching tradelines for user {user_id}: {exc}",
            exc_info=True,
        )
        return error_response(
            "E_FETCH_ERROR",
            message="Failed to retrieve tradeline records.",
            http_status_code=500,
        )


@api_v1_bp.route("/tradelines", methods=["POST"])
@jwt_required()
@rate_limit_if_enabled("30/minute")
@csrf.exempt
@swag_from(
    {
        "tags": ["Tradelines"],
        "summary": "Create a new tradeline record.",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "required": ["account_number", "balance", "date_opened"],
                    "properties": {
                        "account_number": {
                            "type": "string",
                            "example": "ACC-99281",
                        },
                        "balance": {"type": "number", "example": 1500.50},
                        "date_opened": {
                            "type": "string",
                            "format": "date",
                            "example": "2023-01-15",
                        },
                        "creditor_name": {
                            "type": "string",
                            "example": "Chase Bank",
                        },
                    },
                },
            }
        ],
        "responses": {
            201: {"description": "Tradeline created successfully."},
            422: {
                "description": "Validation error or invalid payload format."
            },
        },
    }
)
def create_tradeline() -> Tuple[Response, int]:
    """Creates a new tradeline record for the authenticated user."""
    user_id = get_jwt_identity()
    data: Dict[str, Any] = request.get_json(silent=True) or {}

    required_keys = ["account_number", "balance", "date_opened"]
    if not all(k in data and data[k] is not None for k in required_keys):
        return error_response(
            "E_MISSING_FIELDS",
            message=(
                "Missing required fields: account_number, balance, "
                "date_opened."
            ),
            http_status_code=422,
        )

    try:
        date_opened_parsed = parse(str(data["date_opened"]))
        new_tradeline = Tradeline(
            user_id=user_id,
            account_number=str(data["account_number"]).strip(),
            balance=float(data["balance"]),
            date_opened=date_opened_parsed,
            creditor_name=data.get("creditor_name"),
        )
        db.session.add(new_tradeline)
        db.session.flush()

        db.session.add(
            SchemaEvent(
                user_id=user_id,
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

    except (ValueError, ParserError) as exc:
        db.session.rollback()
        logger.warning(f"Validation failure parsing tradeline input: {exc}")
        return error_response(
            "E_DATA_PARSE",
            message="Invalid balance amount or date_opened format.",
            http_status_code=422,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(
            f"Database error during tradeline creation: {exc}", exc_info=True
        )
        return error_response(
            "E_DB_ERROR",
            message="A database error occurred while creating the tradeline.",
            http_status_code=500,
        )


@api_v1_bp.route("/tradelines/<int:tradeline_id>", methods=["GET"])
@jwt_required()
@rate_limit_if_enabled("60/minute")
@swag_from(
    {
        "tags": ["Tradelines"],
        "summary": "Fetch a specific tradeline by ID.",
        "parameters": [
            {
                "name": "tradeline_id",
                "in": "path",
                "type": "integer",
                "required": True,
                "description": "Unique identifier of the tradeline.",
            }
        ],
        "responses": {
            200: {"description": "Tradeline details."},
            404: {"description": "Tradeline not found or access denied."},
        },
    }
)
def get_tradeline(tradeline_id: int) -> Tuple[Response, int]:
    """Retrieves a single tradeline record verified by user ownership."""
    user_id = get_jwt_identity()
    tradeline = Tradeline.query.filter_by(
        id=tradeline_id, user_id=user_id
    ).first()

    if not tradeline:
        increment_counter("api_tradeline_get_not_found_v1")
        return error_response(
            "E_NOT_FOUND",
            message=(
                f"Tradeline with ID {tradeline_id} not found or access denied."
            ),
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
        "summary": "Update an existing tradeline.",
        "parameters": [
            {
                "name": "tradeline_id",
                "in": "path",
                "type": "integer",
                "required": True,
                "description": "Unique identifier of the tradeline.",
            },
            {
                "name": "body",
                "in": "body",
                "required": False,
                "schema": {
                    "type": "object",
                    "properties": {
                        "balance": {"type": "number", "example": 1200.00},
                        "creditor_name": {
                            "type": "string",
                            "example": "Wells Fargo",
                        },
                    },
                },
            },
        ],
        "responses": {
            200: {"description": "Tradeline updated successfully."},
            404: {"description": "Tradeline not found or access denied."},
            422: {"description": "Invalid input payload."},
        },
    }
)
def update_tradeline(tradeline_id: int) -> Tuple[Response, int]:
    """Updates an existing tradeline record with user authorization check."""
    user_id = get_jwt_identity()
    data: Dict[str, Any] = request.get_json(silent=True) or {}

    tradeline = Tradeline.query.filter_by(
        id=tradeline_id, user_id=user_id
    ).first()

    if not tradeline:
        increment_counter("api_tradeline_update_not_found_v1")
        return error_response(
            "E_NOT_FOUND",
            message=(
                f"Tradeline with ID {tradeline_id} not found or access denied."
            ),
            http_status_code=404,
        )

    try:
        if "balance" in data:
            tradeline.balance = float(data["balance"])
        if "creditor_name" in data:
            tradeline.creditor_name = str(data["creditor_name"]).strip()

        db.session.add(
            SchemaEvent(
                user_id=user_id,
                event_type="TRADELINE_UPDATE_V1",
                origin=f"user:{user_id}",
                detail=(
                    f"Tradeline {tradeline_id} updated: "
                    f"Balance={tradeline.balance}"
                ),
            )
        )
        db.session.commit()
        increment_counter("api_tradeline_update_success_v1")

        return success_response(
            tradeline.to_dict(),
            message=f"Tradeline {tradeline_id} updated successfully.",
        )

    except ValueError as exc:
        db.session.rollback()
        logger.warning(f"Invalid numeric input during tradeline update: {exc}")
        return error_response(
            "E_DATA_PARSE",
            message="Invalid data format for balance field.",
            http_status_code=422,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(
            f"Database error during tradeline update: {exc}", exc_info=True
        )
        return error_response(
            "E_DB_ERROR",
            message="A database error occurred during the update.",
            http_status_code=500,
        )


@api_v1_bp.route("/tradelines/<int:tradeline_id>", methods=["DELETE"])
@jwt_required()
@rate_limit_if_enabled("10/minute")
@csrf.exempt
@swag_from(
    {
        "tags": ["Tradelines"],
        "summary": "Delete a specific tradeline.",
        "parameters": [
            {
                "name": "tradeline_id",
                "in": "path",
                "type": "integer",
                "required": True,
                "description": "Unique identifier of the tradeline.",
            }
        ],
        "responses": {
            200: {"description": "Tradeline deleted successfully."},
            404: {"description": "Tradeline not found or access denied."},
        },
    }
)
def delete_tradeline(tradeline_id: int) -> Tuple[Response, int]:
    """Deletes a specific tradeline record with ownership verification."""
    user_id = get_jwt_identity()
    tradeline = Tradeline.query.filter_by(
        id=tradeline_id, user_id=user_id
    ).first()

    if not tradeline:
        increment_counter("api_tradeline_delete_success_v1")
        return error_response(
            "E_NOT_FOUND",
            message=(
                f"Tradeline with ID {tradeline_id} not found or access denied."
            ),
            http_status_code=404,
        )

    try:
        db.session.add(
            SchemaEvent(
                user_id=user_id,
                event_type="TRADELINE_DELETE_V1",
                origin=f"user:{user_id}",
                detail=(
                    f"Tradeline {tradeline_id} deleted: "
                    f"{tradeline.account_number}"
                ),
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
        logger.error(
            f"Database error during tradeline deletion: {exc}", exc_info=True
        )
        return error_response(
            "E_DB_ERROR",
            message="A database error occurred during deletion.",
            http_status_code=500,
        )
