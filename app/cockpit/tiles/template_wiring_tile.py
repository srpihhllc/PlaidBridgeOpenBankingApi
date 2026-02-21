# =============================================================================
# FILE: app/cockpit/tiles/template_wiring_tile.py
# DESCRIPTION: Cockpit tile to visualize template wiring audit results.
# Reads Redis key audit:template_wiring and renders JSON table.
# =============================================================================

import json

from flask import Blueprint, current_app, jsonify

from app.utils.redis_utils import get_redis_client

template_wiring_tile_bp = Blueprint("template_wiring_tile", __name__)


@template_wiring_tile_bp.route("/cockpit/template_wiring", methods=["GET"])
def template_wiring_tile():
    """
    Cockpit tile: Display template wiring audit results.
    Reads from Redis key 'audit:template_wiring' (emitted by CLI trace-templates).
    """
    redis_client = get_redis_client()
    results = []
    if redis_client:
        try:
            raw = redis_client.get("audit:template_wiring")
            if raw:
                results = json.loads(raw.decode("utf-8"))
        except Exception as e:
            current_app.logger.error(f"Failed to read template wiring audit: {e}")

    # Build response payload
    payload = []
    for r in results:
        payload.append(
            {
                "rule": r.get("rule"),
                "endpoint": r.get("endpoint"),
                "template": r.get("template", "unknown"),
                "status": r.get("status"),
                "error": r.get("error"),
            }
        )

    return jsonify(
        {
            "status": "success",
            "payload": payload,
            "count": len(payload),
        }
    )
