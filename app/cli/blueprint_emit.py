# =============================================================================
# FILE: app/cli/blueprint_emit.py
# DESCRIPTION: CLI command to emit a cockpit-grade blueprint trace into Redis.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace


@click.command("cockpit:emit-blueprint")
@with_appcontext
def blueprint_emit():
    """Emit your blueprint to Redis for cockpit inspection."""
    emit_schema_trace(
        domain="cli",
        event="blueprint_emit",
        detail="status",
        value="success",
        status="ok",
        ttl=300,
        meta={"source": "cli", "command": "cockpit:emit-blueprint"},
    )
    click.echo("✅ Blueprint map emitted")
