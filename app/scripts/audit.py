# =============================================================================
# FILE: app/scripts/audit.py
# DESCRIPTION: Orchestrates all cockpit audits (nav, route, template, relationship, TTL, CLI).
#              Runs them sequentially, prints summary, integrates blueprint/template manifest audit,
#              and emits Redis pulses for operator visibility.
# =============================================================================

import json
import os

from flask import Flask

from app.blueprints import register_blueprints
from app.cli_commands import cli_audit, ttl_audit
from app.utils import nav_audit, relationship_audit, route_audit, template_audit
from app.utils.redis_utils import get_redis_client


def collect_routes(app: Flask):
    """Collect all registered routes and their endpoint/template references."""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(
            {
                "endpoint": rule.endpoint,
                "rule": str(rule),
                "methods": list(rule.methods),
            }
        )
    return routes


def collect_templates(template_root="app/templates"):
    """Walk template directories and collect all template filenames."""
    templates = []
    for root, _, files in os.walk(template_root):
        for f in files:
            if f.endswith((".html", ".htm", ".txt", ".md")):
                rel_path = os.path.relpath(os.path.join(root, f), template_root)
                templates.append(rel_path.replace("\\", "/"))
    return templates


def run_blueprint_template_audit(redis_client=None):
    """
    Audit blueprint/template alignment and emit manifest into Redis.
    """
    app = Flask(__name__)
    register_blueprints(app)

    routes = collect_routes(app)
    templates = collect_templates()

    manifest = []
    for r in routes:
        tpl_candidates = [t for t in templates if r["endpoint"].split(".")[-1] in t]
        manifest.append(
            {
                "endpoint": r["endpoint"],
                "rule": r["rule"],
                "methods": r["methods"],
                "templates_found": tpl_candidates,
                "templates_missing": not tpl_candidates,
            }
        )

    print("📑 Blueprint/Template Manifest:\n")
    print(json.dumps(manifest, indent=2))

    if redis_client:
        try:
            redis_client.setex("audit:blueprint_templates", 600, json.dumps(manifest))
            print("📡 Blueprint/template manifest emitted to Redis (key=audit:blueprint_templates)")
        except Exception as e:
            print(f"⚠️ Failed to emit blueprint/template manifest to Redis: {e}")


def run_all_audits():
    """
    Run all cockpit-grade audits sequentially.
    Prints progress markers and emits Redis pulses for operator dashboards.
    """
    print("🔍 Running cockpit audits...")

    # Execute each audit module
    nav_audit.run()
    route_audit.run()
    template_audit.run()
    relationship_audit.run()
    ttl_audit.run()
    cli_audit.run()

    # Redis client for emissions
    redis_client = get_redis_client()

    # Run integrated blueprint/template manifest audit
    run_blueprint_template_audit(redis_client)

    print("✅ All audits complete")

    # Emit summary pulse into Redis for cockpit visualization
    if redis_client:
        try:
            redis_client.setex("audit:all_audits_summary", 300, "complete")
            print("📡 Audit summary emitted to Redis (key=audit:all_audits_summary)")
        except Exception as e:
            print(f"⚠️ Failed to emit audit summary to Redis: {e}")


if __name__ == "__main__":
    run_all_audits()
