# app/routes/session.py

from flask import Blueprint, current_app, jsonify, request

from app.utils.redis_utils import get_redis_client

session_bp = Blueprint("session", __name__)


@session_bp.route("/session/cache", methods=["POST"])
def cache_session():
    data = request.get_json()
    user_id = data.get("user_id")
    token = data.get("session_token")

    client = getattr(current_app, "redis_client", None) or get_redis_client()
    if client:
        client.setex(f"session:{user_id}", 3600, token)
    else:
        current_app.logger.error(
            f"[session.cache_session] Redis unavailable — skipping setex for session:{user_id} "
            f"(token length: {len(token) if token else 0})"
        )

    return jsonify({"message": "Token cached in Redis"}), 200
