# app/cockpit/tiles/template_audit_tile.py

import json

from flask import Blueprint, render_template

from app.utils.redis_utils import get_redis_client

tile_bp = Blueprint("template_audit_tile", __name__, url_prefix="/cockpit/template_audit")


@tile_bp.route("/", methods=["GET"])
def index():
    r = get_redis_client()

    # Latest run summary (safe decode)
    summary = {
        "templates_scanned": 0,
        "endpoints_found": 0,
        "missing_endpoints": 0,
        "errors": 0,
    }
    try:
        latest_summary = r.get("ttl:template:audit_summary")
        if latest_summary:
            summary.update(json.loads(latest_summary.decode()))
    except Exception:
        pass

    # Historical trend (last 10 runs, safe decode)
    history = []
    try:
        history_raw = r.lrange("template_audit:history", 0, 9)
        for h in history_raw:
            try:
                history.append(json.loads(h.decode()))
            except Exception:
                continue
    except Exception:
        history = []

    return render_template("tiles/template_audit.html", summary=summary, history=history)
