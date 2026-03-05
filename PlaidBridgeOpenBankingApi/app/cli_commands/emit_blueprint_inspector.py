# =============================================================================
# FILE: app/cli_commands/emit_blueprint_inspector.py
# DESCRIPTION: CLI command to emit the current blueprint map into Redis
#              for cockpit-grade introspection. Uses schema-compliant telemetry.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.cockpit.tiles.blueprint_inspector import emit_to_redis
from app.telemetry.ttl_emit import emit_schema_trace
from app.utils.telemetry import log_identity_event


@click.command("emit-blueprint-inspector")
@with_appcontext
def emit_blueprint_inspector():
    """
    Emits the current blueprint map to Redis for cockpit-grade introspection.
    This function runs inside a Flask application context.
    """
    # 1) Gather the raw blueprint metadata
    blueprint_map = emit_to_redis()

    # 2) Emit schema-compliant TTL trace so operators can see freshness
    emit_schema_trace(
        domain="cli",
        event="blueprint_inspector",
        detail="summary",
        value=f"count:{len(blueprint_map)}",
        status="ok",
        ttl=3600,
        meta={
            "source": "cli",
            "total_blueprints": len(blueprint_map),
        },
    )

    # 3) Log an identity event for auditing in your telemetry store
    log_identity_event(
        user_id=0,
        event_type="BLUEPRINT_INSPECTOR_EMIT",
        details={
            "status": "emitted",
            "source": "cli",
            "total_blueprints": len(blueprint_map),
        },
    )

    # 4) Confirmation for the user
    click.echo("✅ Blueprint Inspector TTL emitted to Redis")
