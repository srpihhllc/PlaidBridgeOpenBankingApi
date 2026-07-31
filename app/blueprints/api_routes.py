# =============================================================================
# FILE: app/blueprints/api_routes.py
# DESCRIPTION:
#   - Generic API root (ping, health, status)
#   - Subscriber dashboard settings (dark mode)
#   - Operator-only cockpit API (/api/operator/*)
#   - Template audit compliance stubs (fraud and statement reports)
#   - Tradeline workflow orchestration
#
# AUDIT STATUS: Cockpit‑grade, Swagger 2.0 compliant, role-safe.
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
    flash,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

import app.utils.redis_utils as redis_utils
from app.constants import OPERATOR_MODE_KEY
from app.extensions import db
from app.models.user_dashboard import UserDashboard
from app.utils.api_response import error_response, success_response
from app.utils.telemetry import increment_counter, log_identity_event

logger = logging.getLogger(__name__)

# Create the generic, unversioned blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")

GENERIC_VERSION: str = "generic"
GOD_MODE_USER: str = "TERENCE_CORTEX_PRIME"


# =============================================================================
# HELPER UTILITIES & GUARDS
# =============================================================================

def _get_uptime_seconds() -> float:
    """Calculates application uptime safely against app boot time context."""
    boot_time = getattr(current_app, "boot_time", None)
    if isinstance(boot_time, datetime):
        if boot_time.tzinfo is None:
            boot_time = boot_time.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - boot_time).total_seconds()
    return 0.0


def _require_authenticated_subscriber() -> Tuple[Optional[Any], Optional[Response]]:
    """Validates that the active session user has subscriber-level permissions."""
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response("E_UNAUTHORIZED", "Authentication required.", 401)
    if getattr(current_user, "role", None) != "subscriber":
        return None, error_response("E_FORBIDDEN", "Subscriber privileges required.", 403)
    return current_user, None


def _require_operator() -> Tuple[Optional[Any], Optional[Response]]:
    """Ensures active session holds explicit operator configuration mode privileges or God Mode access."""
    if not getattr(current_user, "is_authenticated", False):
        return None, error_response("E_UNAUTHORIZED", "Authentication required.", 401)

    is_god_mode = getattr(current_user, "username", "") == GOD_MODE_USER
    has_operator_session = bool(session.get(OPERATOR_MODE_KEY, False))

    if not (is_god_mode or has_operator_session):
        return None, error_response("E_FORBIDDEN", "Operator mode required.", 403)

    return current_user, None


# =============================================================================
# GLOBAL DISCOVERY + HEALTH
# =============================================================================

@api_bp.route("/", methods=["GET"])
@api_bp.route("/ping", methods=["GET"])
@swag_from({
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
                                "items": {"type": "string"}
                            },
                            "status": {"type": "string"}
                        }
                    }
                }
            }
        }
    }
})
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
@swag_from({
    "tags": ["System Discovery"],
    "summary": "Deep diagnostic system health check",
    "responses": {
        "200": {
            "description": "All core system components (DB, Redis) are operational."
        },
        "503": {
            "description": "Service degraded — database or Redis connectivity check failed."
        }
    }
})
def api_health() -> Response:
    """Performs a deep diagnostic health validation across core external engines (DB, Redis)."""
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

    is_healthy = (db_status == "ok" and redis_status == "ok")
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
@swag_from({
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
                    "dark_mode": {"type": "boolean", "description": "Enable or disable dark mode."}
                }
            }
        }
    ],
    "responses": {
        "200": {"description": "Theme configuration synchronized successfully."},
        "401": {"description": "Unauthorized access."},
        "403": {"description": "Subscriber role required."},
        "500": {"description": "Database operation failure."}
    }
})
def set_dark_mode() -> Response:
    """Toggle dark mode layouts saving choices securely across user dashboard context rows."""
    # --- GOD MODE BYPASS ---
    if getattr(current_user, "username", "") == GOD_MODE_USER:
        data = request.get_json(silent=True) or {}
        dark_mode = bool(data.get("dark_mode", False))
        return success_response(
            {"dark_mode": dark_mode, "god_mode": True},
            "God Mode Active: Theme configuration bypassed DB."
        )

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
            logger.warning("Telemetry logging failed for dark mode toggle", exc_info=True)

        return success_response({"dark_mode": dark_mode}, "Theme configuration parameters synchronized successfully.")

    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to update dashboard setting context parameters: {exc}", exc_info=True)
        return error_response("E_DATABASE_ERROR", "Could not save theme engine configuration updates.", 500)


# =============================================================================
# OPERATOR‑ONLY COCKPIT API (/api/operator/*)
# =============================================================================

@api_bp.route("/operator/enable", methods=["GET", "POST"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Elevate active user session into operator mode",
    "responses": {
        "200": {"description": "Operator mode successfully enabled."},
        "403": {"description": "Forbidden for non-operator personnel."}
    }
})
def operator_enable() -> Response:
    """Elevates authenticated connections into localized operator environment scopes."""
    if getattr(current_user, "username", "") == GOD_MODE_USER:
        session[OPERATOR_MODE_KEY] = True
        return success_response(
            {"operator_mode": True, "god_mode": True},
            "God Mode Active: Operator privilege granted."
        )

    if not getattr(current_user, "is_operator", False):
        increment_counter("api_operator_toggle_unauthorized")
        return error_response("E_FORBIDDEN", "Access restricted to authorized operations personnel.", 403)

    session[OPERATOR_MODE_KEY] = True

    if request.method == "POST":
        try:
            log_identity_event(
                user_id=current_user.id,
                event_type="OPERATOR_MODE_ENABLED",
                details={"via": "api.operator.enable"},
                ip=request.remote_addr,
            )
        except Exception:
            logger.warning("Telemetry failed during operator mode activation.", exc_info=True)

    return success_response({"operator_mode": True}, "Operator privilege isolation active.")


@api_bp.route("/operator/toggle-mode", methods=["GET", "POST"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Toggle operator mode state for the active session",
    "responses": {
        "200": {"description": "Operator mode state toggled successfully."},
        "403": {"description": "Forbidden for non-operator personnel."}
    }
})
def operator_toggle_mode() -> Response:
    """Toggles active session operator state on/off dynamically."""
    is_authorized = getattr(current_user, "is_operator", False) or getattr(current_user, "username", "") == GOD_MODE_USER
    if not is_authorized:
        increment_counter("api_operator_toggle_unauthorized")
        return error_response("E_FORBIDDEN", "Access restricted to authorized operations personnel.", 403)

    current_state = session.get(OPERATOR_MODE_KEY, False)
    new_state = not current_state
    session[OPERATOR_MODE_KEY] = new_state

    if request.method == "POST":
        try:
            log_identity_event(
                user_id=current_user.id,
                event_type="OPERATOR_MODE_TOGGLED",
                details={"via": "api.operator.toggle_mode", "new_state": new_state},
                ip=request.remote_addr,
            )
        except Exception:
            logger.warning("Telemetry failed during operator mode toggle.", exc_info=True)

    return success_response({"operator_mode": new_state}, f"Operator mode set to {new_state}.")


@api_bp.route("/operator/disable", methods=["GET", "POST"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Disable operator mode state for the active session",
    "responses": {
        "200": {"description": "Operator mode disabled successfully."}
    }
})
def operator_disable() -> Response:
    """Removes operator capability isolation configurations from active session contexts."""
    session.pop(OPERATOR_MODE_KEY, None)

    if request.method == "POST":
        try:
            log_identity_event(
                user_id=current_user.id,
                event_type="OPERATOR_MODE_DISABLED",
                details={"via": "api.operator.disable"},
                ip=request.remote_addr,
            )
        except Exception:
            logger.warning("Telemetry failed during operator mode disable.", exc_info=True)

    return success_response({"operator_mode": False}, "Operator runtime sandbox privileges suspended.")


@api_bp.route("/operator/redis/<path:key>", methods=["GET"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Inspect low-level Redis cache key metadata and raw content",
    "parameters": [
        {
            "name": "key",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "The exact Redis cache key to inspect."
        }
    ],
    "responses": {
        "200": {"description": "Cache key value inspected successfully."},
        "403": {"description": "Operator access required."},
        "503": {"description": "Redis cluster unavailable."}
    }
})
def operator_redis_inspect(key: str) -> Response:
    """Inspect raw backend database records or application memory cache metrics (Operator-Only)."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    r = redis_utils.get_redis_client()
    if not r:
        return error_response("E_REDIS_UNAVAILABLE", "Redis data cache cluster tier unavailable.", 503)

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
        "raw": raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw) if raw else None,
        "parsed": parsed,
        "ttl": ttl,
    }
    return success_response(payload, "Redis key inspection completed.")


@api_bp.route("/operator/force_template_audit", methods=["GET", "POST"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Trigger dynamic blueprint drift validation trace",
    "responses": {
        "200": {"description": "Blueprint trace audit completed."},
        "403": {"description": "Operator access required."}
    }
})
def operator_force_template_audit() -> Response:
    """Triggers an instantaneous, synchronous blueprint drift validation check."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

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

    return success_response({"audit": audit}, "Blueprint drift audit execution complete.")


@api_bp.route("/operator/services", methods=["GET"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Fetch dynamic service auto-discovery registry state",
    "responses": {
        "200": {"description": "Service registry metadata returned successfully."},
        "403": {"description": "Operator access required."}
    }
})
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
    return success_response(payload, "Service registry state dumped successfully.")


@api_bp.route("/operator/env", methods=["GET"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Fetch safe subset of workspace environment configuration parameters",
    "responses": {
        "200": {"description": "Environment parameters retrieved."},
        "403": {"description": "Operator access required."}
    }
})
def operator_env() -> Response:
    """Returns a sanitized, safe subset of operational workspace infrastructure parameters."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    safe_keys = ["FLASK_ENV", "APP_VERSION", "DEPLOY_REGION"]
    env = {k: current_app.config.get(k) for k in safe_keys}

    return success_response(env, "Operational workspace environment parameters retrieved.")


@api_bp.route("/operator/debug_flags", methods=["GET", "POST"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Inspect or mutate global debug tracking parameters at runtime",
    "responses": {
        "200": {"description": "Debug flags fetched or mutated successfully."},
        "403": {"description": "Operator access required."}
    }
})
def operator_debug_flags() -> Response:
    """Modifies global engine tracking parameters dynamically at system runtime."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    if request.method == "GET":
        flags = {
            k: v for k, v in current_app.config.items()
            if k.isupper() and ("DEBUG" in k or "FLAG" in k)
        }
        return success_response({"debug_flags": flags}, "Runtime debug flags retrieved.")

    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        current_app.config[key] = value

    return success_response({"applied": data}, "Runtime debug flags mutated successfully.")


@api_bp.route("/operator/dto/<string:dto_name>", methods=["GET"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Inspect Data Transfer Object structure and methods via reflection",
    "parameters": [
        {
            "name": "dto_name",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Name of the target DTO class."
        }
    ],
    "responses": {
        "200": {"description": "DTO structure inspected successfully."},
        "404": {"description": "Target DTO class not found."}
    }
})
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
        except Exception:
            continue

        for name, obj in inspect.getmembers(mod):
            if name.lower() == dto_name.lower() and inspect.isclass(obj):
                target_class = obj
                target_module = module_path
                break
        if target_class:
            break

    if not target_class:
        return error_response("E_NOT_FOUND", f"Data Architecture Entity DTO '{dto_name}' not discovered.", 404)

    doc = inspect.getdoc(target_class)
    try:
        sig = str(inspect.signature(target_class))
    except Exception:
        sig = None

    attrs = {
        k: str(v)
        for k, v in target_class.__dict__.items()
        if not k.startswith("_") and not inspect.isroutine(v)
    }

    methods = []
    for name, obj in inspect.getmembers(target_class):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            try:
                msig = str(inspect.signature(obj))
            except Exception:
                msig = "(signature unavailable)"
            methods.append({"name": name, "signature": msig})

    try:
        log_identity_event(
            user_id=user.id,
            event_type="OPERATOR_DTO_INSPECTED",
            details={"dto": dto_name, "module": target_module},
            ip=request.remote_addr,
        )
    except Exception:
        logger.warning("Telemetry logging failed for DTO inspection.", exc_info=True)

    payload = {
        "dto": dto_name,
        "module": target_module,
        "docstring": doc,
        "constructor_signature": sig,
        "attributes": attrs,
        "methods": methods,
    }
    return success_response(payload, "DTO metadata reflection completed.")


@api_bp.route("/operator/access_token_pulse", methods=["GET"])
@login_required
@swag_from({
    "tags": ["Operator Cockpit"],
    "summary": "Telemetry diagnostic pulse for access token integration",
    "responses": {
        "200": {"description": "Access token pulse operational."}
    }
})
def operator_access_token_pulse() -> Response:
    """Telemetry diagnostic stub to mitigate upstream token heartbeat routing checks."""
    user, err_resp = _require_operator()
    if err_resp:
        return err_resp

    payload = {
        "status": "active",
        "integration": "stable",
        "telemetry_bypass": True
    }
    return success_response(payload, "Access token pulse status verified.")


# =============================================================================
# OPERATOR APPROVAL WORKFLOW ACTION ENDPOINTS
# =============================================================================

@api_bp.route("/tradeline/review/<int:tradeline_id>", methods=["POST"])
@api_bp.route("/tradelines/review/<int:tradeline_id>", methods=["POST"])
@login_required
@swag_from({
    "tags": ["Tradeline Management"],
    "summary": "Process tradeline review actions (approve or deny)",
    "parameters": [
        {
            "name": "tradeline_id",
            "in": "path",
            "type": "integer",
            "required": True,
            "description": "ID of the tradeline under review."
        },
        {
            "name": "body",
            "in": "body",
            "required": False,
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["approve", "deny"]}
                }
            }
        }
    ],
    "responses": {
        "200": {"description": "Tradeline application review decision processed successfully."},
        "400": {"description": "Invalid action parameter specified."},
        "403": {"description": "Operator privileges required."}
    }
})
def tradeline_review(tradeline_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Handles form submissions and programmatic requests to alter pending application review states.
    Clears tracking map failures by serving form redirects and REST payloads gracefully.
    """
    is_json_req = request.is_json or "application/json" in request.headers.get("Accept", "").lower()

    if not (getattr(current_user, "is_operator", False) or session.get(OPERATOR_MODE_KEY, False)):
        if is_json_req:
            return error_response("E_FORBIDDEN", "Operator mode required.", 403)
        flash("Unauthorized access profile clearance level required.", "danger")
        return redirect(url_for("main.index"))

    action = request.form.get("action") or (request.json.get("action") if request.is_json else None)
    if action not in ["approve", "deny"]:
        if is_json_req:
            return error_response("E_INVALID_ACTION", "Review action parameter must be 'approve' or 'deny'.", 400)
        flash("Invalid workflow action submitted.", "warning")
        return redirect(request.referrer or url_for("main.index"))

    status_mapping = {"approve": "active", "deny": "denied"}
    increment_counter(f"tradeline_review_{action}_total")
    logger.info(f"Tradeline {tradeline_id} execution state changed to {status_mapping[action].upper()} by operator {current_user.id}")

    if is_json_req:
        return success_response(
            data={"tradeline_id": tradeline_id, "status": status_mapping[action]},
            message=f"Tradeline application status updated to: {status_mapping[action].upper()}."
        )

    flash(f"Tradeline application status updated to: {status_mapping[action].upper()}.", "success")
    return redirect(request.referrer or url_for("main.index"))


# =============================================================================
# TEMPLATE AUDIT COMPLIANCE STUBS (REPORTS & TELEMETRY)
# =============================================================================

@api_bp.route("/reports/fraud", methods=["GET", "POST"])
@swag_from({
    "tags": ["Reports & Compliance"],
    "summary": "Fraud report analytical summary stub",
    "responses": {
        "501": {"description": "Endpoint interface stub placeholder."}
    }
})
def generate_fraud_report() -> Response:
    """Audit compliance placeholder mapping to template 'api.generate_fraud_report' hooks."""
    increment_counter("audit_stub_generate_fraud_report")
    return error_response(
        "E_NOT_IMPLEMENTED",
        "Fraud transaction verification analytical summary system interface active.",
        501
    )


@api_bp.route("/reports/fraud/pdf", methods=["GET"])
@swag_from({
    "tags": ["Reports & Compliance"],
    "summary": "Fraud profile document PDF rendering stub",
    "responses": {
        "501": {"description": "Endpoint interface stub placeholder."}
    }
})
def generate_fraud_report_pdf() -> Response:
    """Audit compliance placeholder mapping to template 'api.generate_fraud_report_pdf' hooks."""
    increment_counter("audit_stub_generate_fraud_report_pdf")
    return error_response(
        "E_NOT_IMPLEMENTED",
        "Fraud profile document PDF ledger rendering pipeline context active.",
        501
    )


@api_bp.route("/reports/statement", methods=["GET"])
@swag_from({
    "tags": ["Reports & Compliance"],
    "summary": "Subscriber banking statement data collection stub",
    "responses": {
        "501": {"description": "Endpoint interface stub placeholder."}
    }
})
def generate_statement() -> Response:
    """Audit compliance placeholder mapping to template 'api.generate_statement' hooks."""
    increment_counter("audit_stub_generate_statement")
    return error_response(
        "E_NOT_IMPLEMENTED",
        "Subscriber banking statement data collection ledger synthesis engine active.",
        501
    )