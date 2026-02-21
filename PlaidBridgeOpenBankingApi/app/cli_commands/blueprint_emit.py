# =============================================================================
# FILE: app/cli_commands/blueprint_emit.py
# DESCRIPTION: CLI command to emit a fresh blueprint audit trace into Redis.
#              Uses @with_appcontext for safe context management.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.blueprints.sub_ui_routes import _emit_blueprint_audit_trace
from app.telemetry.ttl_emit import emit_schema_trace


@click.command("blueprint_emit")
@with_appcontext
def blueprint_emit():
    """
    Emits a fresh blueprint audit trace into Redis and prints the results.
    """
    audit = _emit_blueprint_audit_trace()

    # Emit schema-compliant telemetry trace
    emit_schema_trace(
        domain="cli",
        event="blueprint_audit",
        detail="summary",
        value=f"expected:{audit.get('expected')},actual:{audit.get('actual')}",
        status=audit.get("status", "ok"),
        ttl=300,
        meta=audit,
    )

    # Operator feedback
    click.echo("✅ Blueprint audit trace emitted.")
    click.echo(f"Status: {audit.get('status')}")
    click.echo(f"Expected: {audit.get('expected')}, Actual: {audit.get('actual')}")
