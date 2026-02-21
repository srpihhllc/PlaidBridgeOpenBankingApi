# =============================================================================
# FILE: app/cli/emit_blueprint_inspector.py
# DESCRIPTION: CLI command to emit a cockpit-grade blueprint inspector trace
#              into Redis using schema-compliant telemetry.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace


@click.command("cockpit:emit-bp-inspector")
@with_appcontext
def emit_blueprint_inspector():
    """Emit a cockpit blueprint inspector trace."""
    emit_schema_trace(
        domain="cli",
        event="blueprint_inspector",
        detail="status",
        value="success",
        status="ok",
        ttl=300,
        meta={"source": "cli", "command": "cockpit:emit-bp-inspector"},
    )
    click.echo("🔍 Blueprint inspector emitted")
