# =============================================================================
# FILE: app/cockpit/tiles/restart_monitor.py
# DESCRIPTION: Cockpit tile to detect last uWSGI restart type (clean vs crash).
# =============================================================================

from flask import Blueprint, jsonify

from app.utils.redis_utils import get_recent_logs  # Replace with your log reader

restart_monitor_bp = Blueprint("restart_monitor", __name__, url_prefix="/cockpit/restart-monitor")

# Markers for detection
CLEAN_MARKERS = ["goodbye to uWSGI", "VACUUM: unix socket", "*** Starting uWSGI"]
CRASH_MARKERS = [
    "Traceback (most recent call last)",
    "Segmentation Fault",
    "exited on signal",
]


@restart_monitor_bp.route("/status")
def restart_status():
    """
    Returns JSON with the last restart status:
    - ✅ Clean Restart
    - ❌ Crash Detected
    - ⚠️ Unknown State
    """
    logs = get_recent_logs("uwsgi", lines=200)  # Adjust to your log source
    log_text = "\n".join(logs)

    clean_found = all(marker in log_text for marker in CLEAN_MARKERS)
    crash_found = any(marker in log_text for marker in CRASH_MARKERS)

    if crash_found:
        status = "❌ Crash Detected"
        color = "danger"
    elif clean_found:
        status = "✅ Clean Restart"
        color = "success"
    else:
        status = "⚠️ Unknown State"
        color = "warning"

    return jsonify({"status": status, "color": color})
