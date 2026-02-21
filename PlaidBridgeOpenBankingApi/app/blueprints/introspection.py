# app/blueprints/introspection.py

from flask import Blueprint, current_app, render_template, request
from flask_login import login_required

from app.decorators import admin_required
from app.utils.redis_utils import call_reflector_ai, get_redis_client

introspection_bp = Blueprint("introspection", __name__, url_prefix="/introspection")


@introspection_bp.route("/cortex_map")
@login_required
@admin_required
def cortex_map():
    redis = get_redis_client()
    cortex = []
    for key in redis.keys("route_usage:*"):
        endpoint = key.decode().split(":")[1]
        usage = redis.hgetall(key)
        hits = redis.get(f"route_hits:{endpoint}") or 0
        cortex.append(
            {
                "endpoint": endpoint,
                "last_accessed": usage.get("last_accessed"),
                "hits": int(hits),
            }
        )
    cortex.sort(key=lambda x: x["hits"], reverse=True)
    return render_template("admin/cortex_map.html", cortex=cortex)


@introspection_bp.route("/cortex_overlay.svg")
@login_required
@admin_required
def cortex_overlay():
    redis = get_redis_client()
    usage_data = {
        key.decode().split(":")[1]: int(redis.get(key) or 0) for key in redis.keys("route_hits:*")
    }
    return render_template("admin/cortex_overlay.svg", hits=usage_data)


@introspection_bp.route("/diagnose_brain", methods=["GET", "POST"])
@login_required
@admin_required
def diagnose_brain():
    redis = get_redis_client()
    traces = []
    for key in redis.keys("route_usage:*"):
        endpoint = key.decode().split(":")[1]
        usage = redis.hgetall(key)
        hits = redis.get(f"route_hits:{endpoint}") or 0
        traces.append(
            {
                "endpoint": endpoint,
                "hits": hits,
                "last_accessed": usage.get("last_accessed", "Never"),
                "client_ip": usage.get("client_ip", "unknown"),
            }
        )

    traces.sort(key=lambda x: int(x["hits"]), reverse=True)
    analysis_prompt = "\n".join(
        f"- {t['endpoint']} ({t['hits']} hits, last seen {t['last_accessed']})" for t in traces
    )

    if request.method == "POST":
        try:
            insight = call_reflector_ai(analysis_prompt)
        except Exception as e:
            current_app.logger.warning(f"AI reflection failed: {e}")
            insight = "⚠️ Reflection failed. Please try again."
    else:
        insight = (
            "🧠 FinBrain’s neural load favors: "
            f"{traces[0]['endpoint']} ({traces[0]['hits']} hits)\n"
            "Least accessed: "
            f"{traces[-1]['endpoint']} "
            f"(last seen {traces[-1]['last_accessed']})"
        )

    return render_template(
        "admin/brain_diagnosis.html",
        insight=insight,
        traces=traces,
        prompt=analysis_prompt,
    )
