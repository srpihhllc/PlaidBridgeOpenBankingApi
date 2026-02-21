# =============================================================================
# FILE: app/cli_commands/cli_template_audit.py
# DESCRIPTION: CLI command to audit template wiring and endpoint validity.
#              Uses @with_appcontext for safe context management.
# =============================================================================

import click
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
    r = get_redis_client()
    if not r:
        current_app.logger.error("[template_audit] Redis unavailable — cannot emit TTL traces")
        click.echo("❌ Redis unavailable — template audit aborted.")

        # Emit schema-compliant error trace
        emit_schema_trace(
            domain="cli",
            event="template_audit",
            detail="error",
            value="redis_unavailable",
            status="error",
            ttl=300,
            meta={"source": "cli", "reason": "redis_unavailable"},
        )
        return

    try:
        # Expect audit_template_wiring to return a dict summary
        summary = audit_template_wiring(r)
    except Exception as e:
        current_app.logger.error(f"[template_audit] Audit failed: {e}")
        click.echo(f"❌ Template audit failed: {e}")

        # Emit schema-compliant error trace
        emit_schema_trace(
            domain="cli",
            event="template_audit",
            detail="error",
            value="failure",
            status="error",
            ttl=300,
            meta={"source": "cli", "error": str(e)},
        )
        return

    # Emit schema-compliant summary trace
    emit_schema_trace(
        domain="cli",
        event="template_audit",
        detail="summary",
        value="success",
        status="ok",
        ttl=600,
        meta=summary,
    )

    # Structured operator feedback
    click.echo("✅ Template audit complete.")
    click.echo("------------------------------------------------------------")
    click.echo(f"Templates scanned: {summary.get('templates_scanned', 0)}")
    click.echo(f"Endpoints found:  {summary.get('endpoints_found', 0)}")
    click.echo(f"Missing endpoints:{summary.get('missing_endpoints', 0)}")
    click.echo(f"Errors detected:  {summary.get('errors', 0)}")
    click.echo("------------------------------------------------------------")
    click.echo("Check logs and cockpit telemetry for detailed results.")
