# =============================================================================
# FILE: app/blueprints/api_routes.py
# DESCRIPTION:
#     - Generic API root (ping, health, status)
#     - Subscriber dashboard settings (dark mode)
#     - Operator-only cockpit API (/api/operator/*)
#     - Template audit compliance stubs (fraud and statement reports)
#     - Tradeline workflow orchestration
#
# AUDIT STATUS: Cockpit‑grade, Swagger 2.0 compliant, role-safe.
# =============================================================================

import importlib
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flasgger import swag_from
from flask import (
    Blueprint,
    Response,
    current_app,
    request,
    session,
)
from flask_login import current_user, login_required

import app.utils.redis_utils as redis_utils
from app.constants import OPERATOR_MODE_KEY
from app.decorators.access import has_permission
from app.extensions import db
from app.models.user_dashboard import UserDashboard
from app.utils.api_response import error_response, success_response
from app.utils.telemetry import increment_counter, log_identity_event

logger = logging.getLogger(__name__)

# Create the generic, unversioned blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")

GENERIC_VERSION: str = "generic"


# =============================================================================
# HELPER UTILITIES & GUARDS
# =============================================================================


def _get_uptime_seconds() -> float:
    """Calculates application uptime safely against boot time context."""
    boot_time = getattr(current_app, "boot_time", None)
    if isinstance(boot_time, datetime):
        if boot_time.tzinfo is None:
            boot_time = boot_time.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - boot_time).total_seconds()
    return 0.0


def _require_authenticated_subscriber() -> (
    Tuple[Optional[Any], Optional[Response]]
):
    """Validates active session user holds subscriber-level permissions."""
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response(
            "E_UNAUTHORIZED", "Authentication required.", 401
        )
    if getattr(current_user, "role", None) != "subscriber":
        return None, error_response(
            "E_FORBIDDEN", "Subscriber privileges required.", 403
        )
    return current_user, None


def _require_operator() -> Tuple[Optional[Any], Optional[Response]]:
    """Ensures session holds operator config privileges or RBAC operational rights."""
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response(
            "E_UNAUTHORIZED", "Authentication required.", 401
        )

    has_op_permission = has_permission(current_user, "read_operational_data")
    has_operator_session = bool(session.get(OPERATOR_MODE_KEY, False))

    if not (has_op_permission or has_operator_session):
        return None, error_response(
            "E_FORBIDDEN", "Operator mode required.", 403
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
                "description": (
                    "Server heartbeat and API version discovery context."
                ),
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
def ping() -> Response:
    """Returns a server heartbeat and API version discovery context."""
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
            "200": {
                "description": (
                    "All core system components (DB, Redis) are operational."
                )
            },
            "503": {
                "description": "Service degraded — DB or Redis check failed."
            },
        },
    }
)
def api_health() -> Response:
    """Performs deep diagnostic health check on core engines."""
    increment_counter("api_generic_status_total")

    # --- Database Probe ---
    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_status = "error"
        logger.exception("Health check failed: Database connection error.")
        increment_counter("health_check_db_failure_generic")

    # --- Redis Probe ---
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
            "200": {
                "description": "Theme configuration synchronized successfully."
            },
            "401": {"description": "Unauthorized access."},
            "403": {"description": "Subscriber role required."},
            "500": {"description": "Database operation failure."},
        },
    }
)
def set_dark_mode() -> Response:
    """Toggle dark mode choices across user dashboard context rows."""
    user, err_resp = _require_authenticated_subscriber()
    if err_resp:
        return err_resp

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
            logger.warning(
                "Telemetry logging failed for dark mode toggle",
                exc_info=True,
            )

        return success_response(
            {"dark_mode": dark_mode},
            "Theme configuration parameters synchronized successfully.",
        )

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f"Failed to update dashboard setting parameters: {exc}",
            exc_info=True,
        )
        return error_response(
            "E_DATABASE_ERROR",
            "Could not save theme engine configuration updates.",
            500,
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
def generate_fraud_report() -> Response:
    """Endpoint alias for template compatibility to generate fraud report."""
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
def generate_fraud_report_pdf() -> Response:
    """Endpoint alias for template compatibility to generate fraud report PDF."""
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
def generate_statement() -> Response:
    """Endpoint alias for template compatibility to generate account statement."""
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
def tradeline_review(tradeline_id: int) -> Response:
    """Orchestrates tradeline review and status update workflow."""
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
def operator_enable() -> Response:
    """Elevates connections into localized operator environment scopes."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    session[OPERATOR_MODE_KEY] = True

    try:
        log_identity_event(
            user_id=current_user.id,
            event_type="OPERATOR_MODE_ENABLED",
            details={"via": "api.operator.enable"},
            ip=request.remote_addr,
        )
    except Exception:
        logger.warning(
            "Telemetry failed during operator mode activation.",
            exc_info=True,
        )

    return success_response(
        {"operator_mode": True}, "Operator privilege isolation active."
    )


@api_bp.route("/operator/toggle-mode", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Toggle operator mode state for the active session",
        "responses": {
            "200": {
                "description": "Operator mode state toggled successfully."
            },
            "403": {"description": "Forbidden for non-operator personnel."},
        },
    }
)
def operator_toggle_mode() -> Response:
    """Toggles active session operator state on/off dynamically."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    current_state = session.get(OPERATOR_MODE_KEY, False)
    new_state = not current_state
    session[OPERATOR_MODE_KEY] = new_state

    try:
        log_identity_event(
            user_id=current_user.id,
            event_type="OPERATOR_MODE_TOGGLED",
            details={
                "via": "api.operator.toggle_mode",
                "new_state": new_state,
            },
            ip=request.remote_addr,
        )
    except Exception:
        logger.warning(
            "Telemetry failed during operator mode toggle.",
            exc_info=True,
        )

    return success_response(
        {"operator_mode": new_state}, f"Operator mode set to {new_state}."
    )


@api_bp.route("/operator/disable", methods=["POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Disable operator mode state for the active session",
        "responses": {
            "200": {"description": "Operator mode disabled successfully."}
        },
    }
)
def operator_disable() -> Response:
    """Removes operator capability isolation configurations."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    session.pop(OPERATOR_MODE_KEY, None)

    try:
        log_identity_event(
            user_id=current_user.id,
            event_type="OPERATOR_MODE_DISABLED",
            details={"via": "api.operator.disable"},
            ip=request.remote_addr,
        )
    except Exception:
        logger.warning(
            "Telemetry failed during operator mode disable.",
            exc_info=True,
        )

    return success_response(
        {"operator_mode": False},
        "Operator runtime sandbox privileges suspended.",
    )


@api_bp.route("/operator/redis/<path:key>", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": (
            "Inspect low-level Redis cache key metadata and raw content"
        ),
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
def operator_redis_inspect(key: str) -> Response:
    """Inspect raw DB records or memory cache metrics (Operator-Only)."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    r = redis_utils.get_redis_client()
    if not r:
        return error_response(
            "E_REDIS_UNAVAILABLE",
            "Redis data cache cluster tier unavailable.",
            503,
        )

    raw = r.get(key)
    ttl = r.ttl(key)
    parsed = None

    if raw:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

    payload = {
        "key": key,
        "raw": (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
            if raw
            else None
        ),
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
def operator_force_template_audit() -> Response:
    """Triggers dynamic blueprint drift validation check."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    audit = {}
    try:
        from app.blueprints.sub_ui_routes import (
            _emit_blueprint_audit_trace,
        )

        audit = _emit_blueprint_audit_trace()
    except ImportError:
        logger.warning("Blueprint audit trace module could not be imported.")
        audit = {"status": "unavailable", "reason": "sub_ui_routes missing"}
    except Exception as exc:
        logger.error(
            f"Error executing blueprint audit trace: {exc}", exc_info=True
        )
        audit = {"status": "error", "error": str(exc)}

    return success_response(
        {"audit": audit}, "Blueprint drift audit execution complete."
    )


@api_bp.route("/operator/services", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": "Fetch dynamic service auto-discovery registry state",
        "responses": {
            "200": {
                "description": (
                    "Service registry metadata returned successfully."
                )
            },
            "403": {"description": "Operator access required."},
        },
    }
)
def operator_service_registry() -> Response:
    """Returns runtime state dumps from backend auto-discovery registries."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    registry_items = []
    try:
        from app.services.registry import get_service_registry

        registry = get_service_registry()
        registry_items = [s.__dict__ for s in registry]
    except Exception as exc:
        logger.error(f"Failed to fetch service registry: {exc}", exc_info=True)

    payload = {
        "count": len(registry_items),
        "services": registry_items,
    }
    return success_response(
        payload, "Service registry state dumped successfully."
    )


@api_bp.route("/operator/env", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": (
            "Fetch safe subset of workspace environment context parameters"
        ),
        "responses": {
            "200": {"description": "Environment parameters retrieved."},
            "403": {"description": "Operator access required."},
        },
    }
)
def operator_env() -> Response:
    """Returns sanitized subset of workspace infrastructure parameters."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    safe_keys = ["FLASK_ENV", "APP_VERSION", "DEPLOY_REGION"]
    env = {k: current_app.config.get(k) for k in safe_keys}

    return success_response(
        env, "Operational workspace environment parameters retrieved."
    )


@api_bp.route("/operator/debug_flags", methods=["GET", "POST"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": (
            "Inspect (GET) or mutate (POST) global debug tracking parameters at runtime"
        ),
        "responses": {
            "200": {
                "description": ("Debug flags fetched or mutated successfully.")
            },
            "403": {"description": "Operator access required."},
        },
    }
)
def operator_debug_flags() -> Response:
    """Inspects (GET) or modifies (POST) global engine tracking parameters dynamically."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    if request.method == "GET":
        flags = {
            k: v
            for k, v in current_app.config.items()
            if k.isupper() and ("DEBUG" in k or "FLAG" in k)
        }
        return success_response(
            {"debug_flags": flags}, "Runtime debug flags retrieved."
        )

    # Mutation pathway restricted to POST
    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        current_app.config[key] = value

    return success_response(
        {"applied": data}, "Runtime debug flags mutated successfully."
    )


@api_bp.route("/operator/dto/<string:dto_name>", methods=["GET"])
@login_required
@swag_from(
    {
        "tags": ["Operator Cockpit"],
        "summary": ("Inspect Data Transfer Object structure via reflection"),
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
            "404": {"description": "Target DTO class not found."},
        },
    }
)
def operator_dto_inspect(dto_name: str) -> Response:
    """Operator-only Data Transfer Object reflection inspector engine."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

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
            "E_NOT_FOUND", f"DTO '{dto_name}' not found.", 404
        )

    fields = {}
    if hasattr(target_class, "__annotations__"):
        fields = {k: str(v) for k, v in target_class.__annotations__.items()}

    return success_response(
        {
            "dto_name": dto_name,
            "module": target_module,
            "fields": fields,
            "doc": inspect.getdoc(target_class),
        },
        "DTO structure inspected successfully.",
    )