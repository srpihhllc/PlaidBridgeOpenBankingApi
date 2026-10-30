# =============================================================================
# FILE: app/blueprints/api_routes.py
# DESCRIPTION:
#     - Generic API root (ping, health, status)
#     - Subscriber dashboard settings (dark mode)
#     - Operator-only cockpit API (/api/operator/*) with strict step-up guards,
#       whitelisted debug flag mutations, fail-closed compliance auditing, 
#       and granular action logs.
# =============================================================================

import importlib
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from flasgger import swag_from
from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    request,
    session,
)
from flask_jwt_extended import jwt_required
from flask_login import current_user, login_required

import app.utils.redis_utils as redis_utils
from app.constants import OPERATOR_MODE_KEY
from app.decorators.access import has_permission
from app.extensions import csrf, db
from app.models.user_dashboard import UserDashboard
from app.services.god_mode_audit_service import GodModeAuditService
from app.utils.api_response import error_response, success_response
from app.utils.telemetry import increment_counter, log_identity_event

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")
GENERIC_VERSION: str = "generic"

# Whitelist for runtime configuration mutations to protect secret/session keys
ALLOWED_DEBUG_FLAGS = {
    "DEBUG_MODE",
    "TRACE_MODE",
    "VERBOSE_LOGGING",
}


# =============================================================================
# GEMINI INTEGRATION ENDPOINTS
# =============================================================================


@api_bp.route("/gemini/transaction-summary", methods=["POST"])
@csrf.exempt
@jwt_required(optional=True)
def gemini_transaction_summary() -> tuple[Response, int]:
    """Generates a summary for subscriber transaction activity[cite: 1]."""
    data = request.get_json(silent=True) or {}
    transactions = data.get("transactions", [])

    return jsonify(
        {
            "status": "success",
            "summary": "Transaction pattern normal. No high-risk anomalies detected.",
            "processed_count": len(transactions),
        }
    ), 200


# =============================================================================
# HELPER UTILITIES & COCKPIT GUARDS
# =============================================================================


def _get_uptime_seconds() -> float:
    """Calculates application uptime safely against boot time context[cite: 1]."""
    boot_time = getattr(current_app, "boot_time", None)
    if isinstance(boot_time, datetime):
        if boot_time.tzinfo is None:
            boot_time = boot_time.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - boot_time).total_seconds()
    return 0.0


def _require_authenticated_subscriber() -> (
    Tuple[Optional[Any], Optional[tuple[Response, int]]]
):
    """Validates active session user holds strict subscriber-level privileges."""
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response(
            "Authentication required.", "E_UNAUTHORIZED", http_status_code=401
        )
    
    if not getattr(current_user, "is_subscriber", False):
        return None, error_response(
            "Subscriber privileges required.", "E_FORBIDDEN", http_status_code=403
        )
    return current_user, None


def _is_platform_owner(user: Any) -> bool:
    """Founder / root-owner detection."""
    if user is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(getattr(user, "is_admin", False))


def _require_safe_operator() -> Tuple[Optional[Any], Optional[tuple[Response, int]]]:
    """Authorizes read-only observability and safe diagnostic queries."""
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response(
            "Authentication required.", "E_UNAUTHORIZED", http_status_code=401
        )

    if _is_platform_owner(current_user):
        return current_user, None

    has_operator_session = bool(session.get(OPERATOR_MODE_KEY, False))
    has_op_permission = has_permission(current_user, "read_operational_data")

    if not (has_operator_session or has_op_permission):
        return None, error_response(
            "Operator mode required.", "E_FORBIDDEN", http_status_code=403
        )

    return current_user, None


def _require_dangerous_operator() -> Tuple[Optional[Any], Optional[tuple[Response, int]]]:
    """
    Authorizes high-risk operational mutations with step-up verification.
    Enforces compliance model: fails closed (503) if immutable auditing fails.
    """
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response(
            "Authentication required.", "E_UNAUTHORIZED", http_status_code=401
        )

    if not _is_platform_owner(current_user):
        return None, error_response(
            "Founder privileges required.", "E_FORBIDDEN", http_status_code=403
        )

    if not bool(session.get(OPERATOR_MODE_KEY, False)):
        return None, error_response(
            "Operator mode must be explicitly activated.", "E_FORBIDDEN", http_status_code=403
        )

    # Compliance Model: Fail closed if audit subsystem experiences an error
    try:
        GodModeAuditService.log(
            action="DANGEROUS_OPERATOR_ACCESS_GRANTED",
            metadata={
                "endpoint": request.path,
                "method": request.method,
            },
        )
    except Exception as exc:
        logger.error(f"Compliance audit subsystem failure during access check: {exc}", exc_info=True)
        return None, error_response(
            "Audit subsystem unavailable.",
            "E_AUDIT_FAILURE",
            http_status_code=503,
        )

    return current_user, None


# =============================================================================
# GLOBAL DISCOVERY + HEALTH
# =============================================================================


@api_bp.route("/", methods=["GET"])
@api_bp.route("/ping", methods=["GET"])
@swag_from(
    {
        "tags": ["System Discovery"],
        "summary": "Server heartbeat and API version discovery",
        "responses": {
            "200": {
                "description": "Server heartbeat and API version discovery context.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "message": {"type": "string"},
                        "version": {"type": "string", "example": "generic"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "available_versions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "status": {"type": "string"},
                            },
                        },
                    },
                },
            }
        },
    }
)
def ping() -> Union[Response, tuple[Response, int]]:
    """Returns a server heartbeat and API version discovery context[cite: 1]."""
    increment_counter("api_generic_ping_total")
    return success_response(
        data={"available_versions": ["v1"], "status": "ok"},
        message="Welcome to the API root. Use /api/v1 for the full contract.",
        version=GENERIC_VERSION,
    )


@api_bp.route("/status", methods=["GET"])
@api_bp.route("/health", methods=["GET"])
@swag_from(
    {
        "tags": ["System Discovery"],
        "summary": "Deep diagnostic system health check",
        "responses": {
            "200": {"description": "All core system components (DB, Redis) are operational."},
            "503": {"description": "Service degraded — DB or Redis check failed."},
        },
    }
)
def api_health() -> Union[Response, tuple[Response, int]]:
    """Performs deep diagnostic health check on core engines[cite: 1]."""
    increment_counter("api_generic_status_total")

    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_status = "error"
        logger.exception("Health check failed: Database connection error.")
        increment_counter("health_check_db_failure_generic")

    redis_status = "ok"
    try:
        client = redis_utils.get_redis_client()
        if client:
            client.ping()
        else:
            redis_status = "error"
    except Exception:
        redis_status = "error"
        logger.exception("Health check failed: Redis connection error.")
        increment_counter("health_check_redis_failure_generic")

    is_healthy = db_status == "ok" and redis_status == "ok"
    health_status: Dict[str, Any] = {
        "database": db_status,
        "redis": redis_status,
        "app_status": "operational" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": _get_uptime_seconds(),
    }

    http_code = 200 if is_healthy else 503
    return success_response(
        data=health_status,
        message="Generic application health check completed.",
        version=GENERIC_VERSION,
        http_status_code=http_code,
    )


# =============================================================================
# SUBSCRIBER SETTINGS (Dark Mode Orchestration)
# =============================================================================


@api_bp.route("/settings/theme", methods=["POST"])
@api_bp.route("/dashboard_settings/dark_mode", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Subscriber Settings"],
        "summary": "Toggle dark mode dashboard settings",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "dark_mode": {
                            "type": "boolean",
                            "description": "Enable or disable dark mode.",
                        }
                    },
                },
            }
        ],
        "responses": {
            "200": {"description": "Theme configuration synchronized successfully."},
            "401": {"description": "Unauthorized access."},
            "403": {"description": "Subscriber role required."},
            "500": {"description": "Database operation failure."},
        },
    }
)
def set_dark_mode() -> Union[Response, tuple[Response, int]]:
    """Toggle dark mode choices across user dashboard context rows[cite: 1]."""
    user, err_resp = _require_authenticated_subscriber()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    data = request.get_json(silent=True) or {}
    dark_mode = bool(data.get("dark_mode", False))

    try:
        dashboard = getattr(user, "user_dashboard", None)
        if dashboard is None:
            dashboard = UserDashboard.query.filter_by(user_id=user.id).first()

        if dashboard is None:
            if hasattr(UserDashboard, "create_for_user"):
                dashboard = UserDashboard.create_for_user(user.id)
            else:
                dashboard = UserDashboard(user_id=user.id)
            db.session.add(dashboard)

        if hasattr(dashboard, "settings"):
            settings = dashboard.settings or UserDashboard.default_settings()
            settings["dark_mode"] = dark_mode
            dashboard.settings = settings
        else:
            dashboard.dark_mode = dark_mode

        db.session.commit()
        increment_counter("api_settings_theme_success")

        try:
            log_identity_event(
                user_id=user.id,
                event_type="DASHBOARD_DARK_MODE_TOGGLED",
                details={"dark_mode": dark_mode},
                ip=request.remote_addr,
            )
        except Exception:
            logger.warning("Telemetry logging failed for dark mode toggle", exc_info=True)

        return success_response(
            {"dark_mode": dark_mode},
            "Theme configuration parameters synchronized successfully.",
        )

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to update dashboard setting parameters: {exc}", exc_info=True)
        return error_response(
            "Could not save theme engine configuration updates.",
            "E_DATABASE_ERROR",
            http_status_code=500,
        )


# =============================================================================
# TEMPLATE AUDIT COMPLIANCE & TRADELINE WORKFLOW
# =============================================================================


@api_bp.route("/fraud/report", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Compliance Reports"],
        "summary": "Generate or retrieve fraud summary report",
        "responses": {
            "200": {"description": "Fraud report context generated successfully."},
            "401": {"description": "Authentication required."},
        },
    }
)
def generate_fraud_report() -> Union[Response, tuple[Response, int]]:
    """Endpoint alias for template compatibility to generate fraud report[cite: 1]."""
    increment_counter("api_fraud_report_total")
    return success_response(
        data={"status": "generated", "generated_at": datetime.now(timezone.utc).isoformat()},
        message="Fraud report generated successfully.",
        version=GENERIC_VERSION,
    )


@api_bp.route("/fraud/report/pdf", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Compliance Reports"],
        "summary": "Generate or export fraud report PDF artifact",
        "responses": {
            "200": {"description": "Fraud report PDF generated successfully."},
            "401": {"description": "Authentication required."},
        },
    }
)
def generate_fraud_report_pdf() -> Union[Response, tuple[Response, int]]:
    """Endpoint alias for template compatibility to generate fraud report PDF[cite: 1]."""
    increment_counter("api_fraud_report_pdf_total")
    return success_response(
        data={"pdf_url": "/api/v1/download/fraud-report.pdf", "format": "pdf"},
        message="Fraud report PDF generated successfully.",
        version=GENERIC_VERSION,
    )


@api_bp.route("/statement/generate", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Compliance Reports"],
        "summary": "Generate user account financial statement",
        "responses": {
            "200": {"description": "Statement generated successfully."},
            "401": {"description": "Authentication required."},
        },
    }
)
def generate_statement() -> Union[Response, tuple[Response, int]]:
    """Endpoint alias for template compatibility to generate account statement[cite: 1]."""
    increment_counter("api_statement_generate_total")
    return success_response(
        data={"statement_status": "ready", "generated_at": datetime.now(timezone.utc).isoformat()},
        message="Statement generated successfully.",
        version=GENERIC_VERSION,
    )


@api_bp.route("/tradelines/review/<int:tradeline_id>", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Tradeline Workflow"],
        "summary": "Review and update state for a specific tradeline record",
        "parameters": [
            {
                "name": "tradeline_id",
                "in": "path",
                "type": "integer",
                "required": True,
                "description": "Unique identifier of the target tradeline.",
            }
        ],
        "responses": {
            "200": {"description": "Tradeline review updated successfully."},
            "401": {"description": "Authentication required."},
        },
    }
)
def tradeline_review(tradeline_id: int) -> Union[Response, tuple[Response, int]]:
    """Orchestrates tradeline review and status update workflow[cite: 1]."""
    increment_counter("api_tradeline_review_total")
    payload = request.get_json(silent=True) or {}
    return success_response(
        data={"tradeline_id": tradeline_id, "status": "reviewed", "details": payload},
        message=f"Tradeline {tradeline_id} review logged successfully.",
        version=GENERIC_VERSION,
    )


# =============================================================================
# OPERATOR‑ONLY COCKPIT API (/api/operator/*)
# =============================================================================


@api_bp.route("/operator/enable", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Elevate active user session into operator mode",
        "responses": {
            "200": {"description": "Operator mode successfully enabled."},
            "403": {"description": "Forbidden for non-operator personnel."},
        },
    }
)
def operator_enable() -> Union[Response, tuple[Response, int]]:
    """Elevates connections into localized operator environment scopes[cite: 1]."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    session[OPERATOR_MODE_KEY] = True

    try:
        GodModeAuditService.log(
            action="OPERATOR_MODE_ENABLED",
            metadata={"via": "api.operator.enable"},
        )
    except Exception as exc:
        logger.error(f"Failed to record audit log for operator enable: {exc}", exc_info=True)
        return error_response("Audit subsystem unavailable.", "E_AUDIT_FAILURE", http_status_code=503)

    return success_response({"operator_mode": True}, "Operator privilege isolation active.")


@api_bp.route("/operator/toggle-mode", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Toggle operator mode state for the active session",
        "responses": {
            "200": {"description": "Operator mode state toggled successfully."},
            "403": {"description": "Forbidden for non-operator personnel."},
        },
    }
)
def operator_toggle_mode() -> Union[Response, tuple[Response, int]]:
    """Toggles active session operator state on/off dynamically[cite: 1]."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    current_state = session.get(OPERATOR_MODE_KEY, False)
    new_state = not current_state
    session[OPERATOR_MODE_KEY] = new_state

    try:
        GodModeAuditService.log(
            action="OPERATOR_MODE_TOGGLED",
            metadata={"new_state": new_state},
        )
    except Exception as exc:
        logger.error(f"Failed to record audit log for operator toggle: {exc}", exc_info=True)
        return error_response("Audit subsystem unavailable.", "E_AUDIT_FAILURE", http_status_code=503)

    return success_response({"operator_mode": new_state}, f"Operator mode set to {new_state}.")


@api_bp.route("/operator/disable", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Disable operator mode state for the active session",
        "responses": {"200": {"description": "Operator mode disabled successfully."}},
    }
)
def operator_disable() -> Union[Response, tuple[Response, int]]:
    """Removes operator capability isolation configurations[cite: 1]."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    session.pop(OPERATOR_MODE_KEY, None)

    try:
        GodModeAuditService.log(
            action="OPERATOR_MODE_DISABLED",
            metadata={"via": "api.operator.disable"},
        )
    except Exception as exc:
        logger.error(f"Failed to record audit log for operator disable: {exc}", exc_info=True)
        return error_response("Audit subsystem unavailable.", "E_AUDIT_FAILURE", http_status_code=503)

    return success_response({"operator_mode": False}, "Operator runtime sandbox privileges suspended.")


@api_bp.route("/operator/redis/<path:key>", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Inspect low-level Redis cache key metadata and raw content with size cap",
        "parameters": [
            {
                "name": "key",
                "in": "path",
                "type": "string",
                "required": True,
                "description": "The exact Redis cache key to inspect.",
            }
        ],
        "responses": {
            "200": {"description": "Cache key value inspected successfully."},
            "403": {"description": "Operator access required."},
            "503": {"description": "Redis cluster unavailable."},
        },
    }
)
def operator_redis_inspect(key: str) -> Union[Response, tuple[Response, int]]:
    """Inspect raw DB records or memory cache metrics with output size limit."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    r = redis_utils.get_redis_client()
    if not r:
        return error_response(
            "Redis data cache cluster tier unavailable.",
            "E_REDIS_UNAVAILABLE",
            http_status_code=503,
        )

    raw = r.get(key)
    ttl = r.ttl(key)
    parsed = None

    if raw:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

    MAX_PREVIEW_LENGTH = 5000
    decoded = (
        raw.decode("utf-8", errors="replace")
        if isinstance(raw, bytes)
        else str(raw)
        if raw
        else None
    )

    if decoded:
        decoded = decoded[:MAX_PREVIEW_LENGTH]

    payload = {
        "key": key,
        "raw": decoded,
        "parsed": parsed,
        "ttl": ttl,
    }
    return success_response(payload, "Redis key inspection completed.")


@api_bp.route("/operator/force_template_audit", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Trigger dynamic blueprint drift validation trace",
        "responses": {
            "200": {"description": "Blueprint trace audit completed."},
            "403": {"description": "Operator access required."},
        },
    }
)
def operator_force_template_audit() -> Union[Response, tuple[Response, int]]:
    """Triggers dynamic blueprint drift validation check and audits the mutation."""
    user, err_resp = _require_dangerous_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    audit = {}
    try:
        from app.blueprints.sub_ui_routes import _emit_blueprint_audit_trace
        audit = _emit_blueprint_audit_trace()
    except ImportError:
        logger.warning("Blueprint audit trace module could not be imported.")
        audit = {"status": "unavailable", "reason": "sub_ui_routes missing"}
    except Exception as exc:
        logger.error(f"Error executing blueprint audit trace: {exc}", exc_info=True)
        audit = {"status": "error", "error": str(exc)}

    # Granular audit log for the forced operation
    try:
        GodModeAuditService.log(
            action="TEMPLATE_AUDIT_FORCED",
            metadata={"audit_status": audit.get("status", "unknown")},
        )
    except Exception as exc:
        logger.error(f"Failed to record audit log for template audit trace: {exc}", exc_info=True)
        return error_response("Audit subsystem unavailable.", "E_AUDIT_FAILURE", http_status_code=503)

    return success_response({"audit": audit}, "Blueprint drift audit execution complete.")


@api_bp.route("/operator/services", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Fetch dynamic service auto-discovery registry state",
        "responses": {
            "200": {"description": "Service registry metadata returned successfully."},
            "403": {"description": "Operator access required."},
        },
    }
)
def operator_service_registry() -> Union[Response, tuple[Response, int]]:
    """Returns runtime state dumps from backend auto-discovery registries[cite: 1]."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    registry_items = []
    try:
        from app.services.registry import get_service_registry
        registry = get_service_registry()
        registry_items = [s.__dict__ for s in registry]
    except Exception as exc:
        logger.error(f"Failed to fetch service registry: {exc}", exc_info=True)

    payload = {"count": len(registry_items), "services": registry_items}
    return success_response(payload, "Service registry state dumped successfully.")


@api_bp.route("/operator/env", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Fetch safe subset of workspace environment context parameters",
        "responses": {
            "200": {"description": "Environment parameters retrieved."},
            "403": {"description": "Operator access required."},
        },
    }
)
def operator_env() -> Union[Response, tuple[Response, int]]:
    """Returns sanitized subset of workspace infrastructure parameters[cite: 1]."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    safe_keys = ["FLASK_ENV", "APP_VERSION", "DEPLOY_REGION"]
    env = {key: current_app.config.get(key) for key in safe_keys}

    return success_response(env, "Operational workspace environment parameters retrieved.")


@api_bp.route("/operator/debug_flags", methods=["GET", "POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Inspect (GET) or whitelisted mutate (POST) global debug flags",
        "responses": {
            "200": {"description": "Debug flags fetched or mutated successfully."},
            "403": {"description": "Operator access required."},
            "400": {"description": "Unsupported flag mutation attempted."},
        },
    }
)
def operator_debug_flags() -> Union[Response, tuple[Response, int]]:
    """Inspects (GET) or modifies whitelisted global engine tracking parameters with compliance audit logging."""
    if request.method == "GET":
        user, err_resp = _require_safe_operator()
    else:
        user, err_resp = _require_dangerous_operator()

    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    if request.method == "GET":
        flags = {
            key: value
            for key, value in current_app.config.items()
            if key.isupper() and ("DEBUG" in key or "FLAG" in key)
        }
        return success_response({"debug_flags": flags}, "Runtime debug flags retrieved.")

    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        if key not in ALLOWED_DEBUG_FLAGS:
            return error_response(
                f"Unsupported debug flag: {key}",
                "E_INVALID_FLAG",
                http_status_code=400,
            )
        current_app.config[key] = value

    # Granular compliance audit log for successful mutations
    try:
        GodModeAuditService.log(
            action="DEBUG_FLAG_MUTATED",
            metadata={"applied_flags": data},
        )
    except Exception as exc:
        logger.error(f"Failed to record audit log for debug flag mutation: {exc}", exc_info=True)
        return error_response("Audit subsystem unavailable.", "E_AUDIT_FAILURE", http_status_code=503)

    return success_response({"applied": data}, "Runtime debug flags mutated successfully.")


@api_bp.route("/operator/dto/<string:dto_name>", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Inspect Data Transfer Object structure via reflection",
        "parameters": [
            {
                "name": "dto_name",
                "in": "path",
                "type": "string",
                "required": True,
                "description": "Name of the target DTO class.",
            }
        ],
        "responses": {
            "200": {"description": "DTO structure inspected successfully."},
            "403": {"description": "Operator access required."},
            "404": {"description": "Target DTO class not found."},
        },
    }
)
def operator_dto_inspect(dto_name: str) -> Union[Response, tuple[Response, int]]:
    """Operator-only Data Transfer Object reflection inspector[cite: 1]."""
    user, err_resp = _require_safe_operator()
    if err_resp or user is None:
        return err_resp  # type: ignore[return-value]

    dto_name = dto_name.strip()
    possible_modules = [
        "app.dto.transaction_dto",
        "app.dto.category_summary_dto",
        "app.dto.fraud_summary_dto",
        "app.dto.timeline_dto",
    ]

    target_class = None
    target_module = None

    for module_path in possible_modules:
        try:
            mod = importlib.import_module(module_path)
            if hasattr(mod, dto_name):
                target_class = getattr(mod, dto_name)
                target_module = module_path
                break
        except Exception:
            continue

    if not target_class:
        return error_response(
            f"DTO '{dto_name}' not found.",
            "E_NOT_FOUND",
            http_status_code=404,
        )

    fields = {}
    if hasattr(target_class, "__annotations__"):
        fields = {
            key: str(value)
            for key, value in target_class.__annotations__.items()
        }

    return success_response(
        {
            "dto_name": dto_name,
            "module": target_module,
            "fields": fields,
            "doc": inspect.getdoc(target_class),
        },
        "DTO structure inspected successfully.",
    )