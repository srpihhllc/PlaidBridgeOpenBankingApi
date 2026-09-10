# =============================================================================
# FILE: app/cli_commands/endpoint_autofix.py
# DESCRIPTION: Modernized auto-fixer for broken url_for() namespace references.
# =============================================================================

import json
import os
import re

import click
from flask import current_app
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace
from app.utils.redis_utils import get_redis_client

# Matches url_for("endpoint") or url_for('endpoint') with any spacing
URL_FOR_RE = re.compile(r"url_for\(\s*[\"']([^\"']+)[\"']")

# -------------------------------------------------------------------------
# Verified Production-Grade Rewrite Map
# -------------------------------------------------------------------------
ENDPOINT_REWRITE_MAP = {
    # Diagnostics rewires
    "main.db_health": "diagnostics.db_health",
    "main.cache_health": "diagnostics.cache_health",
    # Admin UI rewires
    "main.schema_diagram": "admin.schema_diagram",
    "main.rate_limits_dashboard": "admin.rate_limits_dashboard",
    "main.log_viewer": "admin.log_viewer",
    # Renamed admin functions
    "main.approve_user": "admin.approval_queue",
    "main.delete_redis_key": "admin.sweep_expired_keys",
    # Panel & Tile rewires
    "main.redis_panel": "admin.redis_panel",
    "admin.model_summary_tile": "admin.tile_schema_versions",
    "admin.route_registry_tile": "diagnostics.route_list",
    # Data export & Health
    "main.export_users": "admin_api.admin_list_users",
    "api.health_check": "admin.system_health",
    # Sidebar & Tile Mappings
    "admin.agent_activity": "admin.tile_agent_activity",
    "admin.schema_events": "admin.tile_schema_events",
    "admin.schema_versions": "admin.tile_schema_versions",
    "admin.statements_heatmap": "admin.tile_statements_heatmap",
    "admin.statements_timeline": "admin.tile_statements_timeline",
    # Advanced System Tools
    "admin.route_list": "diagnostics.route_list",
    "admin.brain_diagnosis": "introspection.diagnose_brain",
    "admin.repair_result": "repair.self_repair",
    "admin.schema_viewer": "admin.schema_diagram",
    "admin.db_trace_panel": "admin.tile_trace_viewer",
}


@click.command("endpoint_autofix")
@with_appcontext
def endpoint_autofix():
    """
    Scans templates for legacy endpoint namespaces and rewires them
    to the modern, explicit blueprint topology.
    """
    click.echo("🔍 Starting high-precision endpoint autofix scan...")
    r = None
    try:
        r = get_redis_client()
    except Exception:
        click.echo("⚠️ Redis unavailable — telemetry degraded.")

    env = current_app.jinja_env
    loader = env.loader
    fixes: dict[str, list[tuple[str, str]]] = {}
    patch_output: list[dict[str, str]] = []

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

        patched_source = source
        template_changed = False

        for ep in broken:
            if ep in ENDPOINT_REWRITE_MAP:
                correct = ENDPOINT_REWRITE_MAP[ep]
                if ep != correct:
                    fixes.setdefault(t_name, []).append((ep, correct))

                    # Bulletproof regex replacement: handles spacing and quote style
                    pattern = rf"url_for\(\s*['\"]{re.escape(ep)}['\"]"
                    patched_source, count = re.subn(
                        pattern,
                        f"url_for('{correct}'",
                        patched_source,
                    )

                    if count > 0:
                        template_changed = True
                        patch_output.append(
                            {"template": t_name, "old": ep, "new": correct}
                        )

        if template_changed:
            full_path = os.path.join(
                current_app.root_path, "templates", t_name
            )
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(patched_source)

    # Telemetry and Reporting
    if r:
        emit_schema_trace(
            domain="cli",
            event="endpoint_autofix",
            detail="completed",
            value="success",
            status="ok",
            ttl=600,
            meta={"fixes": fixes},
        )

    click.echo("------------------------------------------------------------")
    click.echo(f"✅ Endpoint Autofix Complete. Patched: {len(fixes)} files.")

    if fixes:
        for tpl, entries in fixes.items():
            for old, new in entries:
                click.echo(f"  {tpl}: {old} → {new}")

    patch_path = "storage/manifest/endpoint_autofix_patch.json"
    os.makedirs(os.path.dirname(patch_path), exist_ok=True)
    with open(patch_path, "w", encoding="utf-8") as f:
        json.dump(patch_output, f, indent=2)
    click.echo(f"📄 Patch manifest secured at {patch_path}")
