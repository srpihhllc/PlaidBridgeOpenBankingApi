# FILE: app/cockpit/tiles/redis_health.py
# DESCRIPTION: Cockpit tile showing Redis connection status and last successful ping timestamp.

from flask import Blueprint, jsonify

from app.utils.redis_utils import REDIS_PING_SUCCESS_TS_KEY, get_redis_client

redis_health = Blueprint("redis_health", __name__)


@redis_health.route("/cockpit/redis_health")
def redis_health_tile():
    """
    Returns JSON with:
      - status: 🟢 OK or 🔴 DOWN
      - last_ping: ISO timestamp of last successful ping, or "never"
    """
    client = get_redis_client()
    last_ping = None
    if client:
        try:
            last_ping = client.get(REDIS_PING_SUCCESS_TS_KEY)
        except Exception:
            last_ping = None

    status = "🟢 OK" if last_ping else "🔴 DOWN"
    return jsonify({"status": status, "last_ping": last_ping or "never"})
