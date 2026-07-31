# =============================================================================
# FILE: app/cli_commands/cli_template_audit.py
# DESCRIPTION: CLI command to audit template wiring and endpoint validity.
#              Hardened for absolute context and telemetry fallback isolation.
# =============================================================================

import sys
import click
import re
from flask import current_app
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace
from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client
from app.utils.template_audit import audit_template_wiring


@click.command("template_audit")
@with_appcontext
def template_audit():
    """
    Scan templates for missing endpoints and emit TTL traces.
    - Checks for required Jinja globals (e.g., 'app')
    - Scans all templates for url_for() calls
    - Verifies that each endpoint exists in the Flask app
    - Emits TTL traces to Redis for cockpit visibility
    - Returns a structured summary for operator clarity
    """
    # 1. Defensively resolve Redis with zero-crash fallbacks
    try:
        r = get_redis_client()
    except Exception as redis_init_err:
        click.echo(f"❌ Critical exception initializing Redis client: {redis_init_err}", err=True)
        r = None

    if not r:
        # Defensively logging via standard stream if current_app proxy behaves unexpectedly
        try:
            current_app.logger.error("[template_audit] Redis unavailable — cannot emit TTL traces")
        except Exception:
            print("[CRITICAL INTERCEPT] [template_audit] Redis unavailable — application proxy unresolvable.", file=sys.stderr)

        click.echo("❌ Redis unavailable — template audit aborted.", err=True)

        # Isolated error tracing fallback
        try:
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="error",
                value="redis_unavailable",
                status="error",
                ttl=300,
                meta={"source": "cli", "reason": "redis_unavailable"},
            )
        except Exception as trace_err:
            click.echo(f"⚠️ Telemetry Intercept: Failed to emit error schema trace: {trace_err}", err=True)
        return

    # 2. Isolate the Core Audit Traversal Engine
    try:
        summary = audit_template_wiring(r)
    except Exception as e:
        try:
            current_app.logger.error(f"[template_audit] Audit failed: {e}")
        except Exception:
            print(f"[CRITICAL INTERCEPT] [template_audit] Audit pipeline failure: {e}", file=sys.stderr)

        click.echo(f"❌ Template audit failed: {e}", err=True)

        try:
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="error",
                value="failure",
                status="error",
                ttl=300,
                meta={"source": "cli", "error": str(e)},
            )
        except Exception:
            pass
        return

    # 3. Emit Final Summary metrics safely
    try:
        emit_schema_trace(
            domain="cli",
            event="template_audit",
            detail="summary",
            value="success",
            status="ok",
            ttl=600,
            meta=summary,
        )
    except Exception as trace_err:
        click.echo(f"⚠️ Telemetry Intercept: Failed to emit completion metrics: {trace_err}", err=True)

    # 4. Structured Operator Reporting
    click.echo("✅ Template audit complete.")
    click.echo("------------------------------------------------------------")
    click.echo(f"Templates scanned: {summary.get('templates_scanned', 0)}")
    click.echo(f"Endpoints found:  {summary.get('endpoints_found', 0)}")
    click.echo(f"Missing endpoints:{summary.get('missing_endpoints', 0)}")
    click.echo(f"Errors detected:  {summary.get('errors', 0)}")
    click.echo("------------------------------------------------------------")
    click.echo("Check logs and cockpit telemetry for detailed results.")