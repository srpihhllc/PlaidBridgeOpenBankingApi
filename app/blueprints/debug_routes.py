# =============================================================================
# FILE: app/blueprints/debug_routes.py
# DESCRIPTION: Hardened debug, health probes, and template audit compliance
#              stubs. Non-destructive operational stubs for operator tooling.
# =============================================================================

import datetime
from datetime import timezone
import logging

from flask import Blueprint, current_app, jsonify, render_template

logger = logging.getLogger(__name__)

# Create the dedicated debug blueprint with structural namespace anchoring
debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


# =============================================================================
# CANONICAL DIAGNOSTIC PROBES
# =============================================================================


@debug_bp.route("/test")
def debug_test():
    """Simple test endpoint that doesn't rely on database models."""
    now = datetime.datetime.now(timezone.utc)
    return (
        jsonify(
            {
                "status": "success",
                "message": "Debug route is working!",
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "utc_now": now.isoformat(),
            }
        ),
        200,
    )


@debug_bp.route("/config")
def debug_config():
    """Return non-sensitive config status and runtime states."""
    try:
        redis_client = getattr(current_app, "redis_client", None)
        redis_ok = False
        if redis_client:
            try:
                redis_client.ping()
                redis_ok = True
            except Exception:
                redis_ok = False

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Configuration probe",
                    "environment": current_app.config.get("ENV", "unknown"),
                    "debug": current_app.config.get("DEBUG", False),
                    "api_version": "1.0",
                    "flask_app_name": current_app.name,
                    "redis_available": redis_ok,
                    "timestamp": datetime.datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    ),
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.exception("Debug config probe failed")
        return jsonify({"status": "error", "details": str(e)}), 500


# =============================================================================
# TEMPLATE AUDIT COMPLIANCE STUBS (NON-DESTRUCTIVE)
# =============================================================================


@debug_bp.route("/self_repair")
def self_repair():
    """
    Lightweight stub for template audit and operator telemetry tooling.
    Returns a consistent JSON payload so static analysis paths resolve properly.
    """
    try:
        payload = {
            "status": "stub",
            "endpoint": "debug.self_repair",
            "message": "Self repair stub endpoint (no-op).",
            "timestamp": (
                datetime.datetime.now(timezone.utc).isoformat() + "Z"
            ),
        }
        return jsonify(payload), 501
    except Exception as exc:
        current_app.logger.exception("debug.self_repair failed: %s", exc)
        return jsonify({"status": "error", "details": str(exc)}), 500


@debug_bp.route("/cortex_map")
def cortex_map():
    """
    Template-backed stub for the cortex map architectural layout tile.
    Renders the target dashboard markup if available; otherwise catches safely
    and returns a clean JSON structure to prevent layout breaks or 404 errors.
    """
    try:
        try:
            return render_template("admin/cortex_map.html")
        except Exception:
            # Fallback block to insulate template discovery from breaking endpoint
            payload = {
                "status": "stub",
                "endpoint": "debug.cortex_map",
                "message": "Cortex map stub (template not available).",
                "timestamp": (
                    datetime.datetime.now(timezone.utc).isoformat() + "Z"
                ),
            }
            return jsonify(payload), 501
    except Exception as exc:
        current_app.logger.exception("debug.cortex_map failed: %s", exc)
        return jsonify({"status": "error", "details": str(exc)}), 500
