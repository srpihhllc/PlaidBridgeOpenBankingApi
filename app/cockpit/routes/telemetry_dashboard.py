# app/cockpit/routes/telemetry_dashboard.py

import redis.exceptions
from flask import Blueprint, current_app, render_template

from app.cockpit.telemetry.emitters.ttl import ttl_summary

cockpit_bp = Blueprint("cockpit_bp", __name__, template_folder="../../templates")


@cockpit_bp.route("/cockpit/telemetry")
def telemetry_dashboard():
    """
    Renders a dashboard visualizing the in-memory TTL pulses and their
    Redis mirror status.
    """
    redis_client = getattr(current_app, "redis_client", None)

    telemetry_data = []
    in_memory_summary = ttl_summary()

    for key, details in in_memory_summary.items():
        redis_status = "N/A"
        redis_ttl = "N/A"
        redis_value = "N/A"

        if redis_client:
            try:
                redis_ttl_val = redis_client.ttl(key)
                if redis_ttl_val > 0:
                    redis_ttl = f"{redis_ttl_val}s"
                    redis_status = "OK"
                    redis_value = redis_client.get(key).decode("utf-8")
                else:
                    redis_status = "EXPIRED"
            except redis.exceptions.ConnectionError:
                redis_status = "ERROR"

        telemetry_data.append(
            {
                "key": key,
                "expires_at": details.get("expires_at"),
                "remaining_seconds": details.get("remaining_seconds"),
                "fresh": details.get("fresh"),
                "redis_status": redis_status,
                "redis_ttl": redis_ttl,
                "redis_value": redis_value,
            }
        )

    fresh_count = sum(1 for item in telemetry_data if item["fresh"] == "True")
    total_count = len(telemetry_data)
    health_percent = round((fresh_count / total_count) * 100, 2) if total_count > 0 else 0

    return render_template(
        "cockpit_dashboard.html",
        data=telemetry_data,
        fresh_count=fresh_count,
        total_count=total_count,
        health_percent=health_percent,
    )
