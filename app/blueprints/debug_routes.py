# =============================================================================
# FILE: app/blueprints/debug_routes.py
# DESCRIPTION: Simple debug routes for testing application health
# =============================================================================

import datetime

from flask import Blueprint, current_app, jsonify  # <-- add current_app here

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


@debug_bp.route("/test")
def debug_test():
    """Simple test endpoint that doesn't rely on models"""
    now = datetime.datetime.utcnow()
    return jsonify(
        {
            "status": "success",
            "message": "Debug route is working!",
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_now": now.isoformat(),
        }
    )


@debug_bp.route("/config")
def debug_config():
    """Return non-sensitive configuration and runtime information"""
    try:
        redis_client = getattr(current_app, "redis_client", None)
        redis_ok = False
        if redis_client:
            try:
                redis_client.ping()
                redis_ok = True
            except Exception:
                redis_ok = False

        return jsonify(
            {
                "status": "success",
                "message": "Configuration probe",
                "environment": current_app.config.get("ENV", "unknown"),
                "debug": current_app.config.get("DEBUG", False),
                "api_version": "1.0",
                "flask_app_name": current_app.name,
                "redis_available": redis_ok,
                "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
    except Exception as e:
        current_app.logger.exception("Debug config probe failed")
        return jsonify({"status": "error", "details": str(e)}), 500
