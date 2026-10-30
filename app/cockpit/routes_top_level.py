# =============================================================================
# FILE: app/cockpit/routes_top_level.py
# DESCRIPTION: Cockpit blueprint exposing job status endpoints and cockpit tiles.
# Provides Redis-backed status lookups with safe fallbacks and logging.
# =============================================================================

from flask import Blueprint, current_app, jsonify

from app.cockpit.tiles.lender_risk_tile import lender_risk_tile_bp
from app.utils.redis_utils import get_job_status

# Group all cockpit routes under /cockpit.
cockpit_bp = Blueprint("cockpit", __name__, url_prefix="/cockpit")

# Mount the tile blueprint under /cockpit.
# Its own URL prefix determines the final tile route.
cockpit_bp.register_blueprint(lender_risk_tile_bp)


@cockpit_bp.route("/job-status/<job_id>", methods=["GET"])
def job_status(job_id: str):
    """Return a background job's status, or a safe fallback response."""
    try:
        status = get_job_status(job_id)
        if status:
            return jsonify(status), 200

        return jsonify({"status": "not_found"}), 200

    except Exception:
        current_app.logger.exception("Cockpit job_status Redis error")
        return jsonify({"status": "error", "detail": "redis_unavailable"}), 503