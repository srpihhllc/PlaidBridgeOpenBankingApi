# app/blueprints/bad_method_probe_tile.py

import json
import time

from flask import Blueprint, jsonify

from app.utils.redis_utils import get_redis_client

probe_bp = Blueprint("probe_bp", __name__)


@probe_bp.route("/cockpit/bad_method_probe", methods=["GET"])
def bad_method_probe_tile():
    redis = get_redis_client()
    now = int(time.time())
    probe_keys = redis.keys("trace:bad_method:*")
    probes = []

    for key in sorted(probe_keys):
        raw = redis.get(key)
        if not raw:
            continue

        trace = json.loads(raw)
        ts_frag = key.split(":")[-1]
        try:
            age = now - int(ts_frag)
        except ValueError:
            age = None

        count_key = f"trace:bad_method_count:{trace.get('ip')}"
        repeat_count = redis.get(count_key)

        probes.append(
            {
                "ip": trace.get("ip"),
                "path": trace.get("path"),
                "method": trace.get("method"),
                "referer": trace.get("referer"),
                "age_seconds": age,
                "repeats": int(repeat_count or 0),
            }
        )

    return jsonify({"traces": probes}), 200
