"""
Cockpit overlay tile: Live Blueprint Drift Details
Consumes TTL pulse from tiles/blueprint_drift_pulse_tile.py
and renders a list of failing blueprints directly in the cockpit UI.
This version hardens the pulse endpoint so it never returns an empty response:
- Prefer a lightweight emitter when available
- Wrap in try/except and always return JSON
- Log exceptions for diagnosis
"""

import logging
import time

from flask import current_app, jsonify

from app.cli_commands import blueprint_drift_tracer
from app.cockpit.telemetry.emitters import ttl

TILE_ID = "blueprint_drift_overlay"
logger = logging.getLogger(__name__)


def render():
    """Full tile render for initial page load."""
    ttl_status = ttl.ttl_summary().get("boot:blueprint_drift", {})
    raw_failures = blueprint_drift_tracer.audit_blueprint_attributes()

    # Normalize failures into dicts for template
    failures = []
    for f in raw_failures:
        # Expecting f to be tuple or object with name/line/link
        failures.append(
            {
                "name": getattr(f, "name", f[0] if isinstance(f, list | tuple) else str(f)),
                "line": getattr(
                    f,
                    "line",
                    f[1] if isinstance(f, list | tuple) and len(f) > 1 else None,
                ),
                "link": getattr(f, "link", None),
            }
        )

    return {
        "title": "Blueprint Drift Details",
        "status": "fail" if failures else "ok",
        "ttl_remaining": ttl_status.get("remaining_seconds"),
        "failures": failures,
        "count": len(failures),
        "last_updated": int(time.time()),
    }


def pulse():
    """
    Lightweight JSON pulse for live TTL/status updates.
    Called by cockpit.js every few seconds to update badge without reload.

    Behaviour:
    - Prefer calls to the lightweight pulse emitter (if available) to reduce work.
    - Always return a JSON response; never return an empty body.
    - Log full exceptions so intermittent server-side crashes/timeouts can be diagnosed.
    """
    try:
        # Prefer the lightweight emitter if available (faster, less I/O)
        try:
            from app.tiles.blueprint_drift_pulse_tile import emit as pulse_emit  # local import
        except Exception:
            pulse_emit = None

        if pulse_emit:
            payload = pulse_emit()
            status = payload.get("status", "error")
            count = int(payload.get("count", 0))
            ttl_remaining = None
            try:
                ttl_status = ttl.ttl_summary().get("boot:blueprint_drift", {})
                ttl_remaining = ttl_status.get("remaining_seconds")
            except Exception:
                ttl_remaining = None

            resp = {
                "status": status,
                "ttl_remaining": ttl_remaining,
                "count": count,
                "last_updated": int(time.time()),
            }
            return jsonify(resp)

        # Fallback: compute via render() (heavier, but safe)
        data = render()
        return jsonify(
            {
                "status": data["status"],
                "ttl_remaining": data["ttl_remaining"],
                "count": data["count"],
                "last_updated": data["last_updated"],
            }
        )

    except Exception as exc:  # ensure we never return an empty response
        # Log the full stacktrace to diagnose intermittent crashes/timeouts
        try:
            current_app.logger.exception("Blueprint drift pulse failed: %s", exc)
        except Exception:
            logger.exception("Blueprint drift pulse failed (no current_app): %s", exc)

        # Always return a safe JSON object so the browser never receives an empty response
        return (
            jsonify(
                {
                    "status": "error",
                    "ttl_remaining": None,
                    "count": 0,
                    "last_updated": int(time.time()),
                    "msg": "pulse failure",
                }
            ),
            500,
        )


if __name__ == "__main__":
    # Manual test mode
    data = render()
    print(f"Status: {data['status']}")
    print(f"TTL Remaining: {data['ttl_remaining']}")
    if data["failures"]:
        print("❌ Drift detected in:")
        for f in data["failures"]:
            print(f"   - {f['name']} (line {f['line']})")
    else:
        print("✅ No blueprint drift detected")
