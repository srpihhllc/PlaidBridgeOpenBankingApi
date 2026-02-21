# app/cockpit/tiles/blueprint_inspector.py

import json

from flask import Blueprint, current_app, jsonify

from app.telemetry.ttl_emit import ttl_emit

tile_blueprint_inspector = Blueprint("tile_blueprint_inspector", __name__)


def inspect_blueprints():
    """
    Gathers URL rules from the Flask app and groups them by blueprint name.
    """
    route_map = [
        {"endpoint": rule.endpoint, "methods": list(rule.methods), "url": str(rule)}
        for rule in current_app.url_map.iter_rules()
    ]

    blueprints = {}
    for bp_name in current_app.blueprints:
        bp_routes = [r for r in route_map if r["endpoint"].startswith(bp_name + ".")]
        blueprints[bp_name] = {"status": "registered", "routes": bp_routes}

    return blueprints


@tile_blueprint_inspector.route("/cockpit/blueprint_inspector")
def blueprint_inspector_tile():
    """
    Returns JSON details of all registered blueprints and emits TTL traces
    so operators can visualize blueprint registration health and payload.
    """
    redis_client = getattr(current_app, "redis_client", None)
    try:
        payload = inspect_blueprints()
        payload_str = json.dumps(payload)

        # Emit a 2-minute TTL trace on success
        ttl_emit(
            key="ttl:cockpit:blueprint_inspector:success",
            msg=payload_str,
            r=redis_client,
            ttl=120,
        )

        return jsonify({"status": "success", "tile": "blueprint_inspector", "payload": payload})

    except Exception as e:
        current_app.logger.exception("⚠️ blueprint_inspector_tile failed")
        ttl_emit(
            key="ttl:cockpit:blueprint_inspector:error",
            msg=f"exception:{str(e)[:128]}",
            r=redis_client,
            ttl=60,
        )
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── ADD THIS AT THE BOTTOM ───────────────────────────────────────────────────

__all__ = ["inspect_blueprints", "emit_to_redis", "tile_blueprint_inspector"]


def emit_to_redis():
    """
    Return the same blueprint map that the /cockpit/blueprint_inspector tile uses.
    The CLI will call this, then emit its own TTL trace and identity event.
    """
    # Must be called under an app context. If you invoke this via a Flask‐CLI
    # command (using @with_appcontext) or wrap in `with app.app_context()`,
    # current_app will be available.
    return inspect_blueprints()
