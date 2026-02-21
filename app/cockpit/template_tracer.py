# =============================================================================
# FILE: app/cockpit/template_tracer.py
# DESCRIPTION: Cockpit-grade template tracer. Iterates over all GET routes,
#              invokes them in a test request context, and records wiring health.
#              Uses PARAMETERIZED_ENDPOINTS to supply safe dummy values.
#              Verifies template existence and auto-creates placeholders.
#              Distinguishes MISSING_TEMPLATE vs ERROR for cockpit dashboard.
# =============================================================================

import os
import traceback
import uuid
from pathlib import Path

from flask import Blueprint, current_app, g, render_template

bp = Blueprint("tracer", __name__, url_prefix="/cockpit")

# Path to templates directory
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

PLACEHOLDER = """{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  <h2>{{ title or "Placeholder" }}</h2>
  <p>Wired and reachable at {{ request.path }}.</p>
</div>
{% endblock %}
"""


def template_exists(template_name: str) -> bool:
    for _root, _, files in os.walk(TEMPLATES_DIR):
        if template_name in files:
            return True
    return False


def create_placeholder(template_name: str) -> str:
    """Create a placeholder template if missing."""
    path = Path(TEMPLATES_DIR) / template_name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(PLACEHOLDER)
    return str(path)


# =============================================================================
# PARAMETERIZED ENDPOINT MAP
# =============================================================================
PARAMETERIZED_ENDPOINTS = {
    "drilldown.drilldown_view": "?file=docs/README.md",
    "api_v1.get_tradeline": "/1",
    "api_v1.get_transaction": "/1",
    "api_v1.get_dispute": "/1",
    "api_v1.get_validation": "/1",
    "admin.view_credit_ledger": "/1",
    "admin.preview_letter": "/1",
    "admin.dispatch_letter3": "/1",
    "admin.view_dispute_logs": "/1",
    "admin.export_trace": "/abc123",
    "admin.identity_source": "/1",
    "main.terence_entry": "",
    "main.dispute_form": "",
    "subscriber.dashboard": "/1",
    "subscriber.update_profile": "/1",
    "sub_ui.dashboard_liquidity": "/1",
    "plaid.link_item": "/test_item",
    "oauth.callback": "?code=dummy&state=test",
    "oauth.token": "/dummy_token",
    "funds.view_fund": "/1",
    "funds.flow": "/1",
    "lenders.view_lender": "/1",
    "letters.dispute_form": "",
    "letters.preview_letter": "/1",
    "letters.dispatch_letter": "/1",
    "webhooks.process_event": "/dummy_event",
    "cockpit.telemetry_dashboard": "",
    "tiles.trace_viewer": "/1",
    "tiles.login_trace_tile": "/1",
}


def trace_templates(app=None):
    app = app or current_app
    results = []

    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods or rule.endpoint.startswith("static"):
            continue

        try:
            view_func = app.view_functions.get(rule.endpoint)
            if not view_func:
                raise ValueError("No view function found")

            g.req_id = str(uuid.uuid4())

            if rule.endpoint in PARAMETERIZED_ENDPOINTS:
                test_url = rule.rule + PARAMETERIZED_ENDPOINTS[rule.endpoint]
            else:
                test_url = rule.rule

            with app.test_request_context(test_url):
                response = view_func()
                if hasattr(response, "status_code") and response.status_code >= 400:
                    raise ValueError(f"Returned status {response.status_code}")

                # Check template existence
                if hasattr(response, "template") and not template_exists(response.template):
                    placeholder_path = create_placeholder(response.template)
                    raise ValueError(f"MISSING_TEMPLATE: Created placeholder at {placeholder_path}")

            results.append(
                {
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "status": "ok",
                    "error": None,
                    "req_id": g.req_id,
                }
            )

        except Exception as e:
            err_text = str(e)
            status = "error"
            if "MISSING_TEMPLATE" in err_text:
                status = "missing_template"
            results.append(
                {
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "status": status,
                    "error": traceback.format_exc(limit=2),
                    "req_id": g.get("req_id", "n/a"),
                }
            )

    return results


@bp.route("/template-tracer")
def template_tracer():
    results = trace_templates()

    telemetry_data = [
        {
            "key": r["endpoint"],
            "expires_at": None,
            "remaining_seconds": 0,
            "fresh": "True" if r["status"] == "ok" else "False",
            "redis_status": (
                "OK"
                if r["status"] == "ok"
                else ("MISSING_TEMPLATE" if r["status"] == "missing_template" else "ERROR")
            ),
            "redis_ttl": "N/A",
            "redis_value": r["error"] or "—",
        }
        for r in results
    ]

    fresh_count = sum(1 for item in telemetry_data if item["fresh"] == "True")
    total_count = len(telemetry_data)
    health_percent = round((fresh_count / total_count) * 100, 2) if total_count > 0 else 0

    return render_template(
        "cockpit/cockpit_dashboard.html",
        data=telemetry_data,
        fresh_count=fresh_count,
        total_count=total_count,
        health_percent=health_percent,
    )
