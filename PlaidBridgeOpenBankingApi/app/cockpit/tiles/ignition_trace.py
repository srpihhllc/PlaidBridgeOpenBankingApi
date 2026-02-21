# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cockpit/tiles/ignition_trace.py

from flask import Blueprint, render_template

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

bp_ignition = Blueprint("ignition_trace", __name__, url_prefix="/cockpit/ignition")


@bp_ignition.route("/")
def render_ignition():
    r = get_redis_client()
    ttl = r.ttl("cortex:subscriber:entry") if r else None
    return render_template("ignition_trace.html", ttl=ttl)
