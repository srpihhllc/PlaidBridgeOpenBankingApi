# app/cockpit/tiles/landing_page_auth_drift.py

from flask import current_app

from app.utils.redis_utils import get_redis_client


def render_landing_page_auth_drift_tile():
    redis = get_redis_client()

    try:
        last_render = redis.get("landing_view_ok")
        ttl = redis.ttl("landing_view_ok")
        status = "✅ healthy" if last_render else "🔴 missing"
        metadata = last_render.decode() if last_render else "n/a"
    except Exception as e:
        status = "❌ Redis error"
        metadata = str(e)
        ttl = "n/a"

    return {
        "tile_id": "landing_page_auth_drift",
        "title": "📡 Landing Page Auth Drift",
        "description": "Monitors landing view success, TTL freshness, and login context injection",
        "status": status,
        "last_rendered": metadata,
        "ttl_remaining": ttl,
        "login_view": current_app.config.get("LOGIN_VIEW", "main.login_form"),
    }
