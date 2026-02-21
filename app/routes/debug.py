# app/routes/debug.py

from datetime import datetime

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db
from app.utils.redis_utils import get_redis_client

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


@debug_bp.route("/db", methods=["GET"])
def db_debug_view():
    client = getattr(current_app, "redis_client", None) or get_redis_client()
    try:
        db.session.execute(text("SELECT 1"))
        now = datetime.utcnow().isoformat()

        if client:
            client.setex("boot:db_ping_success", 1800, "true")
            client.setex("boot:db_ping_success_timestamp", 1800, now)
        else:
            current_app.logger.error("Redis unavailable — skipping DB ping success setex calls")

        return jsonify({"status": "OK", "ping_timestamp": now}), 200

    except Exception as e:
        return jsonify({"status": "ERROR", "error": str(e)}), 500
