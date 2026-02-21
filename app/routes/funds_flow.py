# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/funds_flow.py

import json
from datetime import datetime, timedelta

from flask import Blueprint, current_app, render_template

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL-safe client

funds_flow_bp = Blueprint("funds_flow_bp", __name__, url_prefix="/funds-flow")


@funds_flow_bp.route("/<int:user_id>")
def view_funds_flow(user_id):
    r = get_redis_client()
    flow_data = []

    if r:
        for i in range(7):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            key = f"flow_snapshot:{user_id}:{day}"
            entries = r.lrange(key, 0, -1)

            inbound = outbound = 0
            for entry in entries:
                try:
                    obj = json.loads(entry)
                except (TypeError, json.JSONDecodeError):
                    continue
                amt = obj.get("amount", 0)
                if obj.get("direction") == "inbound":
                    inbound += amt
                else:
                    outbound += amt

            flow_data.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "inbound": inbound,
                    "outbound": outbound,
                    "net": inbound - outbound,
                }
            )
    else:
        current_app.logger.error(
            f"[view_funds_flow] Redis unavailable — no flow data for user_id={user_id}"
        )
        flow_data.append({"date": None, "inbound": None, "outbound": None, "net": None})

    return render_template("funds_flow.html", user_id=user_id, flow_data=flow_data)


@funds_flow_bp.route("/<int:user_id>/anomalies")
def view_anomalies(user_id):
    r = get_redis_client()
    anomalies = []

    if r:
        r_keys = r.keys("vault_anomalies:*")
        for key in r_keys:
            raw_entries = r.lrange(key, 0, -1)
            for entry in raw_entries:
                try:
                    obj = json.loads(entry)
                except (TypeError, json.JSONDecodeError):
                    continue
                if obj.get("borrower_id") == user_id or str(user_id) in key.decode():
                    anomalies.append(obj)
    else:
        current_app.logger.error(
            f"[view_anomalies] Redis unavailable — no anomalies for user_id={user_id}"
        )
        anomalies.append({"error": "Redis unavailable"})

    return render_template("funds_anomalies.html", acct_id=user_id, anomalies=anomalies)
