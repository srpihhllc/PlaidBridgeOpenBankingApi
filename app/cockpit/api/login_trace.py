# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cockpit/api/login_trace.py

import json

from flask import Blueprint, jsonify

from app.utils.redis_utils import get_redis_client

login_trace_api = Blueprint("login_trace_api", __name__)
r = get_redis_client()


@login_trace_api.route("/api/login-trace/<int:user_id>")
def get_login_trace(user_id):
    key = f"pulse:login:{user_id}"
    raw = r.get(key)
    if not raw:
        return jsonify({"status": "no recent login"})

    data = json.loads(raw)
    ttl = r.ttl(key)

    return jsonify(
        {
            "user_email": data.get("email"),
            "status": data.get("status"),
            "mfa_status": data.get("mfa"),
            "timestamp": data.get("timestamp"),
            "ttl_remaining": ttl,
        }
    )
