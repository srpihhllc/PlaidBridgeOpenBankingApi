# =============================================================================
# FILE: app/scripts/audit.py
# DESCRIPTION: Orchestrates all cockpit audits (nav, route, template, relationship, TTL, CLI).
#              Runs them sequentially, prints summary, integrates blueprint/template manifest,
#              and emits Redis pulses for operator visibility.
# =============================================================================

import json
import os
from importlib import import_module
from flask import Flask

from app.blueprints import register_blueprints
from app.utils.redis_utils import get_redis_client
# keep create_app import for producing the app used by audits
from app import create_app


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
    Run all cockpit-grade audits sequentially within a single Flask app context.
    Imports audit modules lazily inside the context so modules that expect
    current_app can safely access it.
    """
    # Create a real app (so modules using current_app work) and run audits inside its context.
    app = create_app()
    with app.app_context():
        print("🔍 Running cockpit audits...")

        # NAV audit: import and run inside the context (nav_audit.audit_templates takes the app)
        try:
            nav_audit = import_module("app.utils.nav_audit")
            print("\n=== NAV TEMPLATE AUDIT ===")
            nav_report = nav_audit.audit_templates(app)
            print(json.dumps(nav_report, indent=2))
        except Exception as e:
            print(f"[ERROR] nav_audit.audit_templates failed: {e}")

        # Helper that imports modules lazily and runs their run() if present
        def _safe_run(module_path: str, name: str):
            try:
                mod = import_module(module_path)
            except Exception as e:
                print(f"[ERROR] failed to import {module_path}: {e}")
                return

            if hasattr(mod, "run"):
                try:
                    print(f"\n▶ Running {name}.run() ...")
                    mod.run()
                except Exception as e:
                    print(f"[ERROR] {name}.run() raised: {e}")
            else:
                print(f"[SKIP] {name} has no run() — skipping.")

        # Run other audits (module paths)
        _safe_run("app.utils.route_audit", "route_audit")
        _safe_run("app.utils.template_audit", "template_audit")
        _safe_run("app.utils.relationship_audit", "relationship_audit")
        _safe_run("app.cli_commands.ttl_audit", "ttl_audit")
        _safe_run("app.cli_commands.cli_audit", "cli_audit")

        # Redis client for emissions (outside the per-module runs we already did)
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
