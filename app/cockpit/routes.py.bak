# =============================================================================
# FILE: app/cockpit/routes.py
# DESCRIPTION: Cockpit blueprint exposing job status endpoints and cockpit tiles.
# Provides Redis-backed status lookups with safe fallbacks and logging.
# =============================================================================

from flask import Blueprint, current_app, jsonify

from app.cockpit.tiles.lender_risk_tile import lender_risk_tile_bp
from app.utils.redis_utils import get_job_status

# Group all cockpit routes under /cockpit
cockpit_bp = Blueprint("cockpit", __name__, url_prefix="/cockpit")

# ✅ Register cockpit tiles
# This exposes: /cockpit/tiles/lender_risk/
cockpit_bp.register_blueprint(lender_risk_tile_bp)


@cockpit_bp.route("/job-status/<job_id>", methods=["GET"])
def job_status(job_id: str):
    """
    Returns the status of a background job by ID.
    - 200 with job status if found
    - 200 with {"status": "not_found"} if missing
    - 503 with {"status": "error"} if Redis unavailable
    """
    try:
        status = get_job_status(job_id)
        if status:
            return jsonify(status), 200
        return jsonify({"status": "not_found"}), 200
    except Exception as e:
        current_app.logger.error(f"❌ Cockpit job_status Redis error: {e}")
        return jsonify({"status": "error", "detail": "redis_unavailable"}), 503
