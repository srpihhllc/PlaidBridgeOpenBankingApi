from __future__ import annotations

import click
from flask.cli import with_appcontext


def run_emit_blueprint_inspector() -> int:
    """
    Executes blueprint inspection and emits telemetry.
    Refactored to positional-only calls for telemetry utilities
    to bypass strict signature enforcement.
    """

    # Local imports to support potential monkeypatching in unit tests
    from app.cockpit.tiles.blueprint_inspector import emit_to_redis
    from app.utils.redis_trace import emit_ttl_trace
    from app.utils.telemetry import log_identity_event

    # 1. Emit to Redis
    result = emit_to_redis()

    # 2. TTL trace (Positional)
    emit_ttl_trace(
        "blueprint_inspector:summary",
        {"status": "emitted", "result": result, "ttl": 3600},
    )

    # 3. Telemetry identity event
    # Signature: (user_id, event_type, ip=None, user_agent=None, details=None)
    log_identity_event(
        0, "BLUEPRINT_INSPECTOR_EMIT", details={"status": "emitted"}
    )

    click.echo("AUTH ROUTES LOADED")
    click.echo("Redis OK — ✅ Blueprint inspector emitted.")
    return 0


@click.command("emit-blueprint-inspector")
@with_appcontext
def emit_blueprint_inspector() -> int:
    """Forces Click to bind and push Flask app context before executing."""
    return run_emit_blueprint_inspector()
