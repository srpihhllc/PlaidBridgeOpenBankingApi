# =============================================================================
# FILE: app/blueprints/api_routes.py
# DESCRIPTION:
#   - Generic API root (ping, health, stats)
#   - Subscriber dashboard settings (dark mode)
#   - Operator-only cockpit API (/api/operator/*)
#
# AUDIT STATUS: Cockpit‑grade, non-conflicting, role-safe.
# =============================================================================

import logging
from datetime import datetime

from flasgger import swag_from
from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required

import app.utils.redis_utils as redis_utils
from app.constants import OPERATOR_MODE_KEY
from app.extensions import db
from app.models.user_dashboard import UserDashboard
from app.security.api_key_auth import require_api_key
from app.utils.api_response import success_response
from app.utils.telemetry import increment_counter, log_identity_event

logger = logging.getLogger(__name__)

# Create the generic, unversioned blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")

GENERIC_VERSION = "generic"

# =============================================================================
# GLOBAL DISCOVERY + HEALTH
# =============================================================================


@api_bp.route("/")
@api_bp.route("/ping")
@swag_from(
    {
        "responses": {
            200: {
                "description": "Server heartbeat and API version discovery.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "available_versions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            }
        }
    }
)
def ping():
    """Returns a server heartbeat and API version info."""
    return success_response(
        data={"available_versions": ["v1"], "status": "ok"},
        message="Welcome to the API root. Use /api/v1 for the full contract.",
        version=GENERIC_VERSION,
    )


@api_bp.route("/api/health")
@swag_from(
    {
        "responses": {
            200: {"description": "Detailed health check of essential services (DB, Redis, etc.)."}
        }
    }
)
def health_check():
    """Performs a deep health check (DB, Redis, etc.)."""

    # --- Database probe ---
    db_status = "ok"
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_status = "error"
        logger.exception("Health check failed: Database connection error.")
        increment_counter("health_check_db_failure_generic")

    # --- Redis probe ---
    redis_status = "ok"
    try:
        client = redis_utils.get_redis_client()
        client.ping()
    except Exception:
        redis_status = "error"
        logger.exception("Health check failed: Redis connection error.")
        increment_counter("health_check_redis_failure_generic")

    timestamp = datetime.utcnow().isoformat() + "Z"
    uptime_seconds = (
        (datetime.utcnow() - current_app.boot_time).total_seconds()
        if hasattr(current_app, "boot_time")
        else 0
    )

    health_status = {
        "database": db_status,
        "redis": redis_status,
        "app_status": ("operational" if db_status == "ok" and redis_status == "ok" else "degraded"),
        "timestamp": timestamp,
        "uptime_seconds": uptime_seconds,
    }

    return success_response(
        data=health_status,
        message="Generic application health check completed.",
        version=GENERIC_VERSION,
        http_status_code=(200 if db_status == "ok" and redis_status == "ok" else 503),
    )


@api_bp.route("/public/stats")
@require_api_key
def public_stats():
    """Public API statistics (API key required)."""
    increment_counter("api_public_stats_access_generic")

    uptime_seconds = (
        (datetime.utcnow() - current_app.boot_time).total_seconds()
        if hasattr(current_app, "boot_time")
        else 0
    )

    stats_data = {
        "total_endpoints": len(current_app.url_map._rules),
        "uptime_seconds": uptime_seconds,
        "data_version": "2024-Q3",
    }

    return success_response(
        data=stats_data,
        message="Public application statistics loaded.",
        version=GENERIC_VERSION,
    )


# =============================================================================
# SUBSCRIBER SETTINGS (Dark Mode)
# =============================================================================


def _require_authenticated_subscriber():
    if not getattr(current_user, "is_authenticated", False):
        return None, ("Unauthorized", 401)
    if getattr(current_user, "role", None) != "subscriber":
        return None, ("Forbidden", 403)
    return current_user, None


@api_bp.route("/dashboard_settings/dark_mode", methods=["POST"])
@login_required
def set_dark_mode():
    """Toggle dark mode for the subscriber dashboard."""
    user, err = _require_authenticated_subscriber()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    data = request.get_json(silent=True) or {}
    dark_mode = bool(data.get("dark_mode", False))

    dashboard = getattr(user, "user_dashboard", None)
    if dashboard is None:
        dashboard = UserDashboard.create_for_user(user.id)
        db.session.add(dashboard)

    settings = dashboard.settings or UserDashboard.default_settings()
    settings["dark_mode"] = dark_mode
    dashboard.settings = settings
    db.session.commit()

    try:
        log_identity_event(
            user_id=user.id,
            event_type="DASHBOARD_DARK_MODE_TOGGLED",
            details={"dark_mode": dark_mode},
            ip=request.remote_addr,
        )
    except Exception:
        pass

    return jsonify({"ok": True, "dark_mode": dark_mode}), 200


# =============================================================================
# OPERATOR‑ONLY COCKPIT API (/api/operator/*)
# =============================================================================


def _require_operator():
    """Operator mode is session‑based, not role‑based."""
    if not getattr(current_user, "is_authenticated", False):
        return None, ("Unauthorized", 401)
    if not session.get(OPERATOR_MODE_KEY, False):
        return None, ("Operator mode required", 403)
    return current_user, None


# --- Enable operator mode -----------------------------------------------------


@api_bp.route("/operator/enable", methods=["POST"])
@login_required
def operator_enable():
    """Enable operator mode for the current authenticated user."""
    user = current_user
    session[OPERATOR_MODE_KEY] = True

    log_identity_event(
        user_id=user.id,
        event_type="OPERATOR_MODE_ENABLED",
        details={"via": "api.operator.enable"},
        ip=request.remote_addr,
    )

    return jsonify({"ok": True, "operator_mode": True}), 200


# --- Disable operator mode ----------------------------------------------------


@api_bp.route("/operator/disable", methods=["POST"])
@login_required
def operator_disable():
    """Disable operator mode."""
    user = current_user
    session.pop(OPERATOR_MODE_KEY, None)

    log_identity_event(
        user_id=user.id,
        event_type="OPERATOR_MODE_DISABLED",
        details={"via": "api.operator.disable"},
        ip=request.remote_addr,
    )

    return jsonify({"ok": True, "operator_mode": False}), 200


# --- Redis key inspector ------------------------------------------------------


@api_bp.route("/operator/redis/<path:key>", methods=["GET"])
@login_required
def operator_redis_inspect(key):
    """Inspect a Redis key (operator‑only)."""
    user, err = _require_operator()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    r = redis_utils.get_redis_client()
    if not r:
        return jsonify({"error": "Redis unavailable"}), 503

    raw = r.get(key)
    ttl = r.ttl(key)

    try:
        import json

        parsed = json.loads(raw) if raw else None
    except Exception:
        parsed = None

    return (
        jsonify(
            {
                "key": key,
                "raw": raw.decode() if raw else None,
                "parsed": parsed,
                "ttl": ttl,
            }
        ),
        200,
    )


# --- Force template audit -----------------------------------------------------


@api_bp.route("/operator/force_template_audit", methods=["POST"])
@login_required
def operator_force_template_audit():
    """Force a subscriber template drift audit."""
    user, err = _require_operator()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    from app.blueprints.sub_ui_routes import _emit_blueprint_audit_trace

    audit = _emit_blueprint_audit_trace()

    return jsonify({"ok": True, "audit": audit}), 200


# --- Service registry inspector ----------------------------------------------


@api_bp.route("/operator/services", methods=["GET"])
@login_required
def operator_service_registry():
    """Return the auto‑discovered service registry."""
    user, err = _require_operator()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    from app.services.registry import get_service_registry

    registry = get_service_registry()

    return (
        jsonify(
            {
                "count": len(registry),
                "services": [s.__dict__ for s in registry],
            }
        ),
        200,
    )


# --- Environment inspector (safe subset) -------------------------------------


@api_bp.route("/operator/env", methods=["GET"])
@login_required
def operator_env():
    """Return a safe subset of environment variables."""
    user, err = _require_operator()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    safe_keys = ["FLASK_ENV", "APP_VERSION", "DEPLOY_REGION"]
    env = {k: current_app.config.get(k) for k in safe_keys}

    return jsonify(env), 200


# --- Toggle global debug flags ------------------------------------------------


@api_bp.route("/operator/debug_flags", methods=["POST"])
@login_required
def operator_debug_flags():
    """Set global debug flags (operator‑only)."""
    user, err = _require_operator()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        current_app.config[key] = value

    return jsonify({"ok": True, "applied": data}), 200


# --- DTO Inspector -----------------------------------------------------------


@api_bp.route("/operator/dto/<string:dto_name>", methods=["GET"])
@login_required
def operator_dto_inspect(dto_name):
    """
    Operator-only DTO inspector.
    Example: /api/operator/dto/TransactionDTO
    """
    user, err = _require_operator()
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    # Normalize input
    dto_name = dto_name.strip()

    # Search DTO modules
    possible_modules = [
        "app.dto.transaction_dto",
        "app.dto.category_summary_dto",
        "app.dto.fraud_summary_dto",
        "app.dto.timeline_dto",
    ]

    target_class = None
    target_module = None

    import importlib
    import inspect

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
        return jsonify({"error": f"DTO '{dto_name}' not found"}), 404

    # Extract metadata
    doc = inspect.getdoc(target_class)
    sig = None
    try:
        sig = str(inspect.signature(target_class))
    except Exception:
        sig = None

    # Class attributes (excluding private + methods)
    attrs = {
        k: v
        for k, v in target_class.__dict__.items()
        if not k.startswith("_") and not inspect.isroutine(v)
    }

    # Methods
    methods = []
    for name, obj in inspect.getmembers(target_class):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            try:
                msig = str(inspect.signature(obj))
            except Exception:
                msig = "(signature unavailable)"
            methods.append({"name": name, "signature": msig})

    # Telemetry
    try:
        log_identity_event(
            user_id=user.id,
            event_type="OPERATOR_DTO_INSPECTED",
            details={"dto": dto_name, "module": target_module},
            ip=request.remote_addr,
        )
    except Exception:
        pass

    return (
        jsonify(
            {
                "dto": dto_name,
                "module": target_module,
                "docstring": doc,
                "constructor_signature": sig,
                "attributes": attrs,
                "methods": methods,
            }
        ),
        200,
    )
