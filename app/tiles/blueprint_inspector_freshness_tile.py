# app/tiles/blueprint_inspector_freshness_tile.py

from flask import Blueprint, jsonify

from app.utils.redis_utils import get_redis_client

tile_blueprint_freshness = Blueprint("tile_blueprint_freshness", __name__)


@tile_blueprint_freshness.route("/tile/blueprint-inspector-freshness")
def render_freshness_tile():
    r = get_redis_client()
    if not r:
        return (
            jsonify(
                {
                    "status": "❌ Redis unavailable",
                    "ttl_seconds": None,
                    "last_payload": None,
                }
            ),
            503,
        )

    key = "ttl:cockpit:blueprint_inspector"
    ttl = r.ttl(key)
    raw = r.get(key)

    status = "✅ Fresh" if ttl and ttl > 0 else "❌ Stale"
    payload = {
        "status": status,
        "ttl_seconds": ttl,
        "last_payload": raw.decode() if raw else None,
    }

    return jsonify(payload)
