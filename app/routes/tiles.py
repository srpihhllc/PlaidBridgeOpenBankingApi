# =============================================================================
# FILE: app/routes/tiles.py
# DESCRIPTION: Cockpit tile routes for operational overlays and pulses.
# =============================================================================

from flask import Blueprint, jsonify

from app.telemetry.ttl_emit import trace_log
from app.tiles import blueprint_drift_overlay_tile
from app.utils.redis_utils import get_redis_client

tiles_bp = Blueprint("tiles", __name__, url_prefix="/tiles")


@tiles_bp.route("/pulse", methods=["GET"])
def pulse_status():
    """
    Returns the full list of current cockpit failures for live overlays.
    Useful for dashboards that aggregate multiple tile statuses.
    """
    redis_client = get_redis_client()
    failures = []

    try:
        # Example: pull all TTL keys matching failure pattern
        keys = redis_client.keys("ttl:failures:*")
        for key in keys:
            data = redis_client.get(key)
            failures.append(
                {
                    "key": key.decode() if isinstance(key, bytes) else key,
                    "value": data.decode() if isinstance(data, bytes) else data,
                }
            )

        trace_log("pulse/fetch", f"Returned {len(failures)} failures.")
        return jsonify({"status": "ok", "failures": failures})

    except Exception as e:
        trace_log("pulse/error", str(e))
        return jsonify({"status": "error", "message": str(e), "failures": []}), 500


@tiles_bp.route("/blueprint_drift_overlay/pulse", methods=["GET"])
def blueprint_drift_overlay_pulse():
    """
    Lightweight JSON endpoint for cockpit.js to poll every few seconds.
    Returns TTL remaining, status, and count of drift failures for the
    Blueprint Drift Overlay tile.
    """
    return blueprint_drift_overlay_tile.pulse()
