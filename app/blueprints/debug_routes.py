# =============================================================================
# FILE: app/blueprints/debug_routes.py
# DESCRIPTION: Hardened debug, health probes, and template audit compliance
#              stubs. Non-destructive operational stubs for operator tooling.
# =============================================================================

import datetime
from datetime import timezone
import logging

from flask import Blueprint, current_app, jsonify, render_template
from flask_login import login_required

from app.decorators import admin_required

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


def _utc_timestamp() -> str:
    return datetime.datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@debug_bp.route("/test")
@login_required
@admin_required
def debug_test():
    """Admin-only diagnostic endpoint."""
    now = datetime.datetime.now(timezone.utc)
    return jsonify({
        "status": "success",
        "message": "Debug route is working.",
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "utc_now": _utc_timestamp(),
    }), 200


@debug_bp.route("/config")
@login_required
@admin_required
def debug_config():
    """Return non-sensitive configuration status."""
    redis_client = getattr(current_app, "redis_client", None)
    redis_ok = False

    if redis_client is not None:
        try:
            redis_client.ping()
            redis_ok = True
        except Exception:
            current_app.logger.exception("Redis check failed in debug config probe")

    return jsonify({
        "status": "success",
        "message": "Configuration probe",
        "environment": current_app.config.get("ENV", "unknown"),
        "debug": bool(current_app.config.get("DEBUG", False)),
        "api_version": "1.0",
        "flask_app_name": current_app.name,
        "redis_available": redis_ok,
        "timestamp": _utc_timestamp(),
    }), 200


@debug_bp.route("/self_repair")
@login_required
@admin_required
def self_repair():
    """Non-destructive stub for operator tooling."""
    return jsonify({
        "status": "stub",
        "endpoint": "debug.self_repair",
        "message": "Self-repair stub endpoint (no-op).",
        "timestamp": _utc_timestamp(),
    }), 501


@debug_bp.route("/cortex_map")
@login_required
@admin_required
def cortex_map():
    """Render the cortex map, or return a safe stub if unavailable."""
    try:
        return render_template("admin/cortex_map.html")
    except Exception:
        current_app.logger.exception("Could not render debug cortex map")
        return jsonify({
            "status": "stub",
            "endpoint": "debug.cortex_map",
            "message": "Cortex map is unavailable.",
            "timestamp": _utc_timestamp(),
        }), 501
