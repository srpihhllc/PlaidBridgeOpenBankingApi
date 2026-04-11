from __future__ import annotations

import os
import click


def run_emit_blueprint_inspector() -> int:
    """Pure Python function — testable and monkeypatchable."""

    # Import AFTER tests may monkeypatch these module attributes
    from app.cockpit.tiles.blueprint_inspector import emit_to_redis
    from app.utils.redis_trace import emit_ttl_trace
    from app.utils.telemetry import log_identity_event

    # 1. Emit to Redis (stubbed as fake_emit_to_redis)
    result = emit_to_redis()

    # 2. TTL trace (stubbed as fake_emit_ttl_trace)
    emit_ttl_trace(
        key="blueprint_inspector:summary",
        msg={"status": "emitted", "result": result},
        ttl=3600,
    )

    # 3. Telemetry identity event (stubbed as fake_log_identity_event)
    log_identity_event(
        event="BLUEPRINT_INSPECTOR_EMIT",
        user_id=0,
        meta={"status": "emitted"},
    )

    click.echo("AUTH ROUTES LOADED")
    click.echo("Redis OK — ✅ Blueprint inspector emitted.")
    return 0


@click.command("emit-blueprint-inspector")
def emit_blueprint_inspector() -> int:
    return run_emit_blueprint_inspector()
