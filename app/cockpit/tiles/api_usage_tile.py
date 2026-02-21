# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cockpit/tiles/api_usage_tile.py

from flask import Blueprint, render_template

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

bp_api_usage = Blueprint("api_usage_tile", __name__, url_prefix="/cockpit/api-usage")


@bp_api_usage.route("/")
def render_api_usage():
    r = get_redis_client()
    usage = r.get("apikey:account:usage") or "Clear"
    return render_template("api_usage_tile.html", usage=usage)
