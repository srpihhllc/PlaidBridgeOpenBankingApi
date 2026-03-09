# app/cockpit/telemetry_tracer.py

import datetime
import traceback

from flask import Blueprint, g, render_template

from app.telemetry.ttl_emit import trace_log
from app.utils.telemetry import log_identity_event

bp = Blueprint("telemetry_tracer", __name__)


def trace_telemetry():
    results = []

    try:
        g.req_id = g.get("req_id", "telemetry-test")
        trace_log("telemetry_tracer", {"status": "test", "req_id": g.req_id})
        log_identity_event(
            event_type="telemetry_tracer",
            details={"actor": "system", "req_id": g.req_id},
        )

        results.append({"status": "ok", "error": None, "req_id": g.req_id})
    except Exception as e:
        results.append(
            {
                "status": "error",
                "error": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc(limit=2)}",
                "req_id": g.get("req_id", "n/a"),
            }
        )

    return results


@bp.route("/telemetry-tracer")
def telemetry_tracer():
    results = trace_telemetry()
    return render_template(
        "admin/template_tracer.html",
        results=results,
        timestamp=datetime.datetime.utcnow(),
    )
