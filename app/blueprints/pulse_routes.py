# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/pulse_routes.py

# =============================================================================
# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/pulse_routes.py
# Pulse & Telemetry Routes
# =============================================================================

from datetime import datetime, timezone

from flask import Blueprint, jsonify, make_response
from sqlalchemy import text

from app.extensions import db

pulse_bp = Blueprint("pulse", __name__, url_prefix="/pulse")


@pulse_bp.route("/healthz", methods=["GET"])
def healthz():
    """Health check endpoint with guaranteed key presence for schema tests."""
    payload = {
        "status": "healthy",
        "database": {"status": "unknown", "online": False},
    }
    status_code = 200

    try:
        db.session.execute(text("SELECT 1"))
        payload["database"] = {"status": "healthy", "online": True}
    except Exception as exc:
        payload["status"] = "degraded"
        payload["database"] = {
            "status": "unhealthy",
            "online": False,
            "error": str(exc),
        }
        status_code = 503

    resp = make_response(jsonify(payload), status_code)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@pulse_bp.route("/tiles/blueprint_drift_overlay/pulse", methods=["GET"])
def blueprint_drift_pulse():
    """Satisfy cockpit.js polling for blueprint drift monitoring."""
    payload = {
        "status": "ok",
        "ttl_remaining": 300,
        "failures": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = make_response(jsonify(payload), 200)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@pulse_bp.route("/vault/<int:vault_id>", methods=["GET"])
def vault_pulse(vault_id):
    payload = {"vault_id": vault_id, "status": "ok", "data": None}
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "public, max-age=5"
    return resp


@pulse_bp.route("/access_token/<int:token_id>", methods=["GET"])
def access_token_pulse(token_id):
    payload = {"token_id": token_id, "status": "ok", "data": None}
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "public, max-age=5"
    return resp