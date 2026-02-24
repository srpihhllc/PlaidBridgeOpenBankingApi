# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cockpit/tiles/login_trace_monitor.py

from flask import Blueprint, render_template

from app.utils.redis_utils import get_redis_client  # ✅ centralised client

# Define the blueprint
bp_login_trace_monitor = Blueprint(
    "login_trace_monitor", __name__, url_prefix="/cockpit/login-trace-monitor"
)

# Alias it as bp_login so other modules can import consistently
bp_login = bp_login_trace_monitor


@bp_login_trace_monitor.route("/")
def render_login_trace_monitor():
    r = get_redis_client()
    trace = r.get("login:trace:monitor") if r else None
    return render_template("login_trace_monitor.html", trace=trace)
