#!/usr/bin/env python3
from pathlib import Path

# List of templates reported missing by the test run
missing = [
    "admin/cockpit/lender_risk_day_detail.html",
    "admin/cockpit/lender_risk_day_invalid.html",
    "admin/cockpit/lender_risk_overview.html",
    "admin/neural_console.html",
    "admin_console.html",
    "admin_dispute_logs.html",
    "admin_letter_preview.html",
    "agent_activity.html",
    "api_usage_tile.html",
    "audit_viewer.html",
    "auth/account_settings.html",
    "auth/change_password.html",
    "auth/reset_password.html",
    "brain_diagnosis.html",
    "cache_health.html",
    "cockpit/trace_detail.html",
    "cockpit/trace_not_found.html",
    "cockpit_dashboard.html",
    "cortex_map.html",
    "credit_dashboard.html",
    "dashboard_anomalies.html",
    "dashboard_liquidity.html",
    "error.html",
    "fallback_tile.html",
    "foo/bar.html",
    "foreign_key_drift_tile.html",
    "fraud_charts.html",
    "identity_events.html",
    "ignition_trace.html",
    "lenders.html",
    "log_viewer.html",
    "login_trace_monitor.html",
    "me.html",
    "model_summary.html",
    "mutation_submit_tile.html",
    "operator_login.html",
    "rate_limits.html",
    "redis_panel.html",
    "registry.html",
    "repair_result.html",
    "route_list.html",
    "schema_events.html",
    "schema_versions.html",
    "schema_viewer.html",
    "sql_panel.html",
    "statements_heatmap.html",
    "statements_timeline.html",
    "system_health.html",
    "system_heartbeat.html",
    "system_map.html",
    "telemetry_dashboard.html",
    "test_email.html",
    "trace_viewer.html",
    "trace_viewer_tile.html",
    "tradelines_panel.html",
]

TEMPLATES_ROOT = Path("app/templates")

PLACEHOLDER = """{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  <h2>{{ title or "Placeholder" }}</h2>
  <p>Placeholder for template: {tpl}</p>
  <p>Wired and reachable at {{ request.path }}.</p>
</div>
{% endblock %}
"""

created = []
skipped = []

for tpl in missing:
    path = TEMPLATES_ROOT / tpl
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        skipped.append(str(path))
        continue

    # Use replace() to avoid Python interpreting Jinja braces
    path.write_text(PLACEHOLDER.replace("{tpl}", tpl))
    created.append(str(path))

print("Created:", len(created))
for p in created:
    print("  ", p)

print("Skipped (already exist):", len(skipped))
for p in skipped[:10]:
    print("  ", p)
