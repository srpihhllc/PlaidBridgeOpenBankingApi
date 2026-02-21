# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/anomaly_routes.py

import json
from datetime import datetime, timedelta

from flask import Blueprint, current_app, render_template

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

anomaly_bp = Blueprint("anomaly_bp", __name__, url_prefix="/dashboard")


@anomaly_bp.route("/anomalies")
def anomaly_dashboard():
    r = get_redis_client()
    high_count = medium_count = low_count = 0
    anomaly_labels = []
    anomaly_counts = []

    if r:
        for i in range(7):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            anomaly_labels.append(day.strftime("%Y-%m-%d"))
            keys = r.keys("vault_anomalies:*")
            count = 0

            for key in keys:
                entries = r.lrange(key, 0, -1)
                for entry in entries:
                    try:
                        obj = json.loads(entry)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    ts = obj.get("timestamp", "")
                    if ts.startswith(str(day)):
                        count += 1
                        for flag in obj.get("flags", []):
                            if "High-Value" in flag or "Unknown Method" in flag:
                                high_count += 1
                            elif "Zero Balance" in flag:
                                medium_count += 1
                            else:
                                low_count += 1

            anomaly_counts.append(count)
    else:
        current_app.logger.error("[anomaly_dashboard] Redis unavailable — no anomaly data loaded")

    return render_template(
        "dashboard_anomalies.html",
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        anomaly_labels=anomaly_labels,
        anomaly_counts=anomaly_counts,
    )


@anomaly_bp.route("/anomalies/<int:acct_id>")
def trace_viewer(acct_id):
    r = get_redis_client()
    anomalies = []

    if r:
        raw = r.lrange(f"vault_anomalies:{acct_id}", 0, -1)
        for entry in raw:
            try:
                anomalies.append(json.loads(entry))
            except (TypeError, json.JSONDecodeError):
                continue
    else:
        current_app.logger.error(
            f"[trace_viewer] Redis unavailable — cannot load anomalies for acct_id={acct_id}"
        )

    return render_template("anomalies_trace.html", acct_id=acct_id, anomalies=anomalies)


@anomaly_bp.route("/log-asset-degradation", methods=["POST"])
def log_asset_degradation():
    client = getattr(current_app, "redis_client", None) or get_redis_client()

    if client:
        try:
            client.setex("asset:styles_health", 900, "degraded")  # 🧨 TTL 15 min
        except Exception as e:
            current_app.logger.error(
                f"[log_asset_degradation] Failed to set asset:styles_health in Redis: {e}"
            )
    else:
        current_app.logger.error(
            "[log_asset_degradation] Redis unavailable — skipping setex for asset:styles_health"
        )

    return ("Logged", 200)
