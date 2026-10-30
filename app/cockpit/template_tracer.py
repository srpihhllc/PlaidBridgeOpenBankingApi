# =============================================================================
# FILE: app/cockpit/template_tracer.py
# DESCRIPTION: Cockpit-grade template tracer. Iterates over routes and requests
#              them through Flask's test client, recording wiring health.
#              Supplies safe dummy values for parameterized routes.
#              Distinguishes missing templates and auth-blocked routes.
# =============================================================================

import os
import traceback
import uuid
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

from flask import Blueprint, current_app, render_template

bp = Blueprint("tracer", __name__, url_prefix="/cockpit")

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


# Endpoint-specific URL values. Route arguments are passed to Werkzeug's
# URL builder; "query" values are appended as query parameters.
PARAMETERIZED_ENDPOINTS = {
    "drilldown.drilldown_view": {"query": {"file": "docs/README.md"}},
    "api_v1.get_tradeline": {},
    "api_v1.get_transaction": {},
    "api_v1.get_dispute": {},
    "api_v1.get_validation": {},
    "admin.view_credit_ledger": {},
    "admin.preview_letter": {},
    "admin.dispatch_letter3": {},
    "admin.view_dispute_logs": {},
    "admin.export_trace": {},
    "admin.identity_source": {},
    "main.terence_entry": {},
    "main.dispute_form": {},
    "subscriber.dashboard": {},
    "subscriber.update_profile": {},
    "sub_ui.dashboard_liquidity": {},
    "plaid.link_item": {},
    "oauth.callback": {"query": {"code": "dummy", "state": "test"}},
    "oauth.token": {},
    "funds.view_fund": {},
    "funds.flow": {},
    "lenders.view_lender": {},
    "letters.dispute_form": {},
    "letters.preview_letter": {},
    "letters.dispatch_letter": {},
    "webhooks.process_event": {},
    "cockpit.telemetry_dashboard": {},
    "tiles.trace_viewer": {},
    "tiles.login_trace_tile": {},
    "pulse.vault_pulse": {},
    "pulse.access_token_pulse": {},
}


def _dummy_value_for_argument(rule: Any, argument: str) -> Any:
    """Return a safe value appropriate for a rule's URL converter."""
    converter = rule._converters.get(argument)
    converter_name = converter.__class__.__name__ if converter else ""

    if converter_name == "IntegerConverter":
        return 1
    if converter_name == "FloatConverter":
        return 1.0
    if converter_name == "UUIDConverter":
        return "00000000-0000-0000-0000-000000000001"
    if converter_name in {"PathConverter", "AnyConverter"}:
        return "sample"
    return "sample"


def _build_test_url(app: Any, rule: Any, method: str) -> str:
    """Build a concrete URL for a rule, including query parameters."""
    endpoint_config = PARAMETERIZED_ENDPOINTS.get(rule.endpoint, {})
    if not isinstance(endpoint_config, dict):
        endpoint_config = {}

    values = {
        argument: _dummy_value_for_argument(rule, argument)
        for argument in rule.arguments
    }
    values.update(
        {
            key: value
            for key, value in endpoint_config.items()
            if key != "query" and key in rule.arguments
        }
    )

    adapter = app.url_map.bind("localhost")
    url = adapter.build(
        rule.endpoint,
        values=values,
        method=method,
        force_external=False,
    )

    query = endpoint_config.get("query", {})
    if query:
        url = f"{url}?{urlencode(query)}"

    return cast(str, url)


def trace_templates(app: Any = None) -> list[dict[str, Any]]:
    app = app or current_app
    results = []
    client = app.test_client()

    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("static"):
            continue

        methods = set(rule.methods or []) - {"HEAD", "OPTIONS"}
        if not methods:
            continue

        if "GET" not in methods and rule.endpoint not in PARAMETERIZED_ENDPOINTS:
            continue

        req_id = str(uuid.uuid4())

        try:
            method = "GET" if "GET" in methods else sorted(methods)[0]
            test_url = _build_test_url(app, rule, method)

            response = client.open(
                test_url,
                method=method,
                headers={"X-Trace-Request-ID": req_id},
            )

            if response.status_code == 401:
                results.append(
                    {
                        "endpoint": rule.endpoint,
                        "rule": rule.rule,
                        "status": "auth_blocked",
                        "error": "Endpoint requires authentication.",
                        "req_id": req_id,
                    }
                )
                continue

            if response.status_code >= 400:
                raise ValueError(f"Returned status {response.status_code}")

            # Flask's test-client response does not normally expose the
            # template name rendered by the view. Keep this check for
            # responses that do expose it.
            template_name = getattr(response, "template", None)
            if template_name and not template_exists(template_name):
                placeholder_path = create_placeholder(template_name)
                raise ValueError(
                    f"MISSING_TEMPLATE: Created placeholder at {placeholder_path}"
                )

            results.append(
                {
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "status": "ok",
                    "error": None,
                    "req_id": req_id,
                }
            )

        except Exception as exc:
            status = (
                "missing_template"
                if "MISSING_TEMPLATE" in str(exc)
                else "error"
            )
            results.append(
                {
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "status": status,
                    "error": traceback.format_exc(limit=2),
                    "req_id": req_id,
                }
            )

    return results


@bp.route("/template-tracer")
def template_tracer() -> str:
    results = trace_templates()

    telemetry_data = [
        {
            "key": result["endpoint"],
            "expires_at": None,
            "remaining_seconds": 0,
            "fresh": "True" if result["status"] == "ok" else "False",
            "redis_status": (
                "OK"
                if result["status"] == "ok"
                else (
                    "MISSING_TEMPLATE"
                    if result["status"] == "missing_template"
                    else (
                        "AUTH_BLOCKED"
                        if result["status"] == "auth_blocked"
                        else "ERROR"
                    )
                )
            ),
            "redis_ttl": "N/A",
            "redis_value": result["error"] or "—",
        }
        for result in results
    ]

    fresh_count = sum(
        1 for item in telemetry_data if item["fresh"] == "True"
    )
    total_count = len(telemetry_data)
    health_percent = (
        round((fresh_count / total_count) * 100, 2) if total_count else 0
    )

    return render_template(
        "cockpit/cockpit_dashboard.html",
        data=telemetry_data,
        fresh_count=fresh_count,
        total_count=total_count,
        health_percent=health_percent,
    )