# =============================================================================
# FILE: app/cli_commands/combined_template_endpoint_audit.py
# DESCRIPTION: Unified cockpit-grade audit for template wiring + endpoint drift.
#              Performs both audits, applies autofixes, emits telemetry, and
#              produces a patch manifest.
# =============================================================================

import json
import os
import re

import click
from flask import current_app
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace
from app.utils.redis_utils import get_redis_client
from app.utils.template_audit import audit_template_wiring

URL_FOR_RE = re.compile(r"url_for\(\s*[\"']([^\"']+)[\"']")

# -------------------------------------------------------------------------
# Mapping table: broken_endpoint → correct_endpoint
# Extend this as needed.
# -------------------------------------------------------------------------
ENDPOINT_REWRITE_MAP = {
    "main.delete_rate_limit": "admin.tile_rate_limits",
    "main.sweep_expired_keys": "admin.sweep_expired_keys",
    "main.approve_user": "admin.approve_user",
    "main.export_users": "admin.export_users",
    "main.debug_db": "admin.db_trace_panel",
    "main.redis_panel": "admin.redis_panel",
    "admin.model_summary": "admin.model_summary_tile",
    "admin.export_traces": "admin.export_trace",
    "auth.login_google": "auth.login",
    "api.health_check": "diagnostics.system_health",
    "admin.dispute_logs": "admin.view_dispute_logs",
    "admin.route_registry_tile": "admin.route_registry_tile",
}


@click.command("audit-all")
@with_appcontext
def audit_all():
    """
    Combined Template Wiring Audit + Endpoint Autofix.
    - Scans all templates for dangling url_for() references
    - Detects missing endpoints
    - Applies autofixes using rewrite map
    - Emits cockpit telemetry
    - Writes patch manifest
    """

    click.echo("🔍 Starting combined template + endpoint audit...")
    redis_client = None

    # ---------------------------------------------------------------------
    # 1. Redis Initialization
    # ---------------------------------------------------------------------
    try:
        redis_client = get_redis_client()
    except Exception as e:
        click.echo(f"⚠️ Redis unavailable: {e}")
        redis_client = None

    # ---------------------------------------------------------------------
    # 2. Run Template Wiring Audit
    # ---------------------------------------------------------------------
    click.echo("📡 Running template wiring audit...")
    try:
        wiring_summary = audit_template_wiring(redis_client)
    except Exception as e:
        click.echo(f"❌ Template wiring audit failed: {e}")
        wiring_summary = {"errors": 1}

    # ---------------------------------------------------------------------
    # 3. Endpoint Autofix
    # ---------------------------------------------------------------------
    click.echo("🛠️ Running endpoint autofix...")
    env = current_app.jinja_env
    loader = env.loader

    fixes = {}
    patch_output = []

    for t_name in env.list_templates():
        if not t_name.endswith(".html"):
            continue

        try:
            source, _, _ = loader.get_source(env, t_name)
        except Exception:
            continue

        broken = URL_FOR_RE.findall(source)
        if not broken:
            continue

        for ep in broken:
            if ep in ENDPOINT_REWRITE_MAP:
                correct = ENDPOINT_REWRITE_MAP[ep]
                if ep != correct:
                    fixes.setdefault(t_name, []).append((ep, correct))

                    patched = source.replace(
                        f"url_for('{ep}')", f"url_for('{correct}')"
                    )
                    patched = patched.replace(
                        f'url_for("{ep}")', f'url_for("{correct}")'
                    )

                    patch_output.append(
                        {"template": t_name, "old": ep, "new": correct}
                    )

                    full_path = os.path.join(
                        current_app.root_path, "templates", t_name
                    )
                    with open(full_path, "w") as f:
                        f.write(patched)

    # ---------------------------------------------------------------------
    # 4. Telemetry Emission
    # ---------------------------------------------------------------------
    if redis_client:
        emit_schema_trace(
            domain="cli",
            event="combined_audit",
            detail="completed",
            value="success",
            status="ok",
            ttl=600,
            meta={"template_wiring": wiring_summary, "endpoint_fixes": fixes},
        )

    # ---------------------------------------------------------------------
    # 5. Operator Report
    # ---------------------------------------------------------------------
    click.echo("------------------------------------------------------------")
    click.echo("✅ Combined Template + Endpoint Audit Complete")
    click.echo(
        f"Templates scanned: {wiring_summary.get('templates_scanned', 0)}"
    )
    click.echo(
        f"Missing endpoints: {wiring_summary.get('missing_endpoints', 0)}"
    )
    click.echo(f"Autofix templates patched: {len(fixes)}")
    click.echo(
        f"Total autofixes applied: {sum(len(v) for v in fixes.values())}"
    )
    click.echo("------------------------------------------------------------")

    if fixes:
        click.echo("🔧 Autofixes applied:")
        for tpl, entries in fixes.items():
            click.echo(f"  {tpl}:")
            for old, new in entries:
                click.echo(f"    - {old} → {new}")
    else:
        click.echo("🎉 No endpoint fixes required — system is clean.")

    # ---------------------------------------------------------------------
    # 6. Patch Manifest
    # ---------------------------------------------------------------------
    patch_path = "storage/manifest/combined_endpoint_patch.json"
    os.makedirs(os.path.dirname(patch_path), exist_ok=True)
    with open(patch_path, "w") as f:
        json.dump(patch_output, f, indent=2)

    click.echo(f"📄 Patch manifest written to {patch_path}")
