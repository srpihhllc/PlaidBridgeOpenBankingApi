# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/repair.py

import os
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template
from flask_login import login_required

from app.decorators import admin_required
from app.utils.redis_utils import get_redis_client

repair_bp = Blueprint("repair", __name__, url_prefix="/repair")


@repair_bp.route("/system_heartbeat")
@login_required
@admin_required
def system_heartbeat():
    try:
        wsgi_path = "/var/www/srpihhllc_pythonanywhere_com_wsgi.py"
        timestamp = os.path.getmtime(wsgi_path)
        restart_time = datetime.utcfromtimestamp(timestamp)
        return render_template(
            "admin/system_heartbeat.html",
            restart_time=restart_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
    except Exception as e:
        current_app.logger.exception("Unable to fetch heartbeat timestamp")
        return jsonify({"error": "Could not read WSGI mtime", "details": str(e)}), 500


@repair_bp.route("/self_repair", methods=["POST"])
@login_required
@admin_required
def self_repair():
    redis = get_redis_client()
    repaired = []
    for key in redis.keys("mfa_code:*"):
        if redis.ttl(key) == -1:
            redis.expire(key, 300)
            repaired.append(key.decode())
    return render_template(
        "admin/repair_result.html", repaired_keys=repaired, repaired_count=len(repaired)
    )


@repair_bp.route("/clear-zombies", methods=["POST"])
@login_required
@admin_required
def clear_zombie_sessions():
    """Surgically purges Redis keys with no TTL starting with mfa, rate, or session."""
    try:
        redis_client = get_redis_client()
        keys = redis_client.keys("*")
        purged_count = 0
        for k in keys:
            if redis_client.ttl(k) == -1:
                key_str = k.decode()
                if key_str.startswith(("mfa", "rate", "session")):
                    redis_client.delete(k)
                    purged_count += 1
        return jsonify({"success": True, "purged": purged_count}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
