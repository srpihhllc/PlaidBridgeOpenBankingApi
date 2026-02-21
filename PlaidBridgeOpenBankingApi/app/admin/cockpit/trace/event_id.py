# app/admin/cockpit/trace/event_id.py

import json

from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.redis_utils import get_redis_client

trace_bp = Blueprint("trace_event", __name__)


@trace_bp.route("/admin/cockpit/trace/<event_id>")
@login_required
def trace_detail(event_id):
    redis_conn = get_redis_client()
    key = f"identity_event:{event_id}"
    raw = redis_conn.get(key)

    if not raw:
        return render_template("cockpit/trace_not_found.html", event_id=event_id), 404

    event = json.loads(raw)
    return render_template("cockpit/trace_detail.html", event=event)
