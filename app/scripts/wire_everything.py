# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/wire_everything.py
# =============================================================================
# PURPOSE:
#   This script now ONLY ensures missing templates exist.
#   It NO LONGER creates or registers any UI blueprints.
#   It NO LONGER creates the ghost "admin_ui" blueprint.
#   It NO LONGER injects anything into blueprint registries.
#
#   This version is fully aligned with the real blueprint namespace:
#       admin.admin_index
#       admin.route_registry_tile
#
#   No shadow blueprints. No endpoint drift. No collisions.
# =============================================================================

from pathlib import Path

# === 1. Create missing templates with placeholders ===
missing_templates = [
    "cockpit/trace_not_found.html",
    "cockpit/trace_detail.html",
    "registry.html",
    "test_email.html",
    "foreign_key_drift_tile.html",
    "statements_dashboard.html",
    "api_usage_tile.html",
    "ignition_trace.html",
    "login_trace_monitor.html",
    "mutation_submit_tile.html",
    "fallback_tile.html",
    "me.html",
    "system_health.html",
]

placeholder = """{% extends "base.html" %}
{% block content %}
<div class="container py-4">
  <h2>{{ title or "Placeholder" }}</h2>
  <p>Wired and reachable at {{ request.path }}.</p>
</div>
{% endblock %}
"""

for tpl in missing_templates:
    path = Path("app/templates") / tpl
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(placeholder)
        print(f"Created placeholder: {path}")
    else:
        print(f"Exists: {path}")

# =============================================================================
# 2. REMOVED: UI blueprint generation
#    (sub_ui, admin_ui) — these caused endpoint drift and BuildErrors.
# =============================================================================

# =============================================================================
# 3. REMOVED: Automatic injection into app/blueprints/__init__.py
#    (This prevented ghost blueprints from being registered.)
# =============================================================================

print("=== Wire-up complete. No UI blueprints created. No injections performed. ===")
