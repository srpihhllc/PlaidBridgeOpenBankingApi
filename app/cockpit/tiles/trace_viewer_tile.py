# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cockpit/tiles/trace_viewer_tile.py

import json
import time

from flask import Blueprint, current_app, render_template

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

bp_trace_viewer = Blueprint("trace_viewer_tile", __name__, url_prefix="/cockpit/trace-viewer")


@bp_trace_viewer.route("/")
def render_trace_viewer():
    r = get_redis_client()
    if not r:
        current_app.logger.error("[trace_viewer_tile] Redis unavailable — cannot load traces")
        return render_template("fallback_tile.html", error="Redis unavailable — cannot load traces")

    try:
        keys = r.keys("trace:*")
        traces = []

        for key in sorted(keys, reverse=True):  # Newest first
            ttl = r.ttl(key)
            raw = r.get(key)
            if raw:
                try:
                    payload = json.loads(raw)
                    traces.append(
                        {
                            "key": key.decode() if isinstance(key, bytes) else key,
                            "event_type": payload.get("event_type"),
                            "detail": payload.get("detail"),
                            "timestamp": _format_timestamp(payload.get("timestamp")),
                            "ttl": ttl,
                            "freshness": classify_freshness(ttl),
                        }
                    )
                except Exception as e:
                    traces.append(
                        {
                            "key": key.decode() if isinstance(key, bytes) else key,
                            "event_type": "decode_error",
                            "detail": str(e),
                            "timestamp": "N/A",
                            "ttl": ttl,
                            "freshness": "error",
                        }
                    )

        return render_template("trace_viewer_tile.html", traces=traces)

    except Exception as e:
        current_app.logger.error(f"[trace_viewer_tile] Error rendering traces: {e}")
        return render_template("fallback_tile.html", error=f"Trace viewer error: {str(e)}")


def classify_freshness(ttl):
    if ttl < 30:
        return "⚠️ Stale"
    elif ttl > 3600:
        return "🌀 Excessive"
    elif ttl < 0:
        return "❌ Expired"
    else:
        return "✅ Healthy"


def _format_timestamp(ts):
    """
    Safely format a timestamp (epoch seconds or ISO string) for display.
    """
    try:
        if isinstance(ts, int | float):
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        elif isinstance(ts, str):
            # If it's an ISO string, just return it
            return ts
    except Exception:
        pass
    return "N/A"
