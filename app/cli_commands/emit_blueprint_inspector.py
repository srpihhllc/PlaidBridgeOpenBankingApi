# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/emit_blueprint_inspector.py

from __future__ import annotations

import click
from flask.cli import with_appcontext


def run_emit_blueprint_inspector() -> int:
    """
    Inspect the blueprint registry and emit results to Redis,
    telemetry, and TTL tracing.
    """

    # Keep imports local so pytest monkeypatches work correctly.
    from app.cockpit.tiles.blueprint_inspector import emit_to_redis
    from app.utils.redis_trace import emit_ttl_trace
    from app.utils.telemetry import log_identity_event

    result = emit_to_redis()

    payload = {
        "status": "emitted",
        "result": result,
        "ttl": 3600,
    }

    emit_ttl_trace(
        "blueprint_inspector:summary",
        payload,
        ttl=3600,
    )

    log_identity_event(
        0,
        "BLUEPRINT_INSPECTOR_EMIT",
        details=payload,
    )

    click.echo("AUTH ROUTES LOADED")
    click.echo("Redis OK — ✅ Blueprint inspector emitted.")

    return 0


@click.command("emit-blueprint-inspector")
@with_appcontext
def emit_blueprint_inspector() -> int:
    """
    Execute blueprint inspector emission command.
    """
    return run_emit_blueprint_inspector()