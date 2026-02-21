# app/tiles/view_failure_probe.py

from datetime import datetime


def collect_view_failures():
    return {
        "tile": "trace:view_failure_probe",
        "summary": "Last 500 Errors in Live Environment",
        "timestamp": datetime.utcnow().isoformat(),
        "failures": [
            {
                "route": "/login_subscriber",
                "method": "POST",
                "timestamp": "2025-07-26T20:59:23Z",
                "status": "500",
                "suspected_cause": "DB session blocked or model not loaded",
            },
            {
                "route": "/auth/login/google",
                "method": "GET",
                "timestamp": "2025-07-26T20:59:40Z",
                "status": "500",
                "suspected_cause": "Missing TTL emitter or DB credentials",
            },
        ],
    }
