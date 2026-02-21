# app/cli/grant_pulse.py

import json

import click

from app.telemetry.ttl_emit import trace_log
from app.utils.redis_utils import get_redis_client


@click.command("cockpit:grant-pulse")
def grant_pulse():
    """Show live Redis-based grant composition stats."""
    # Emit cockpit telemetry
    trace_log("cli/grant_pulse/status", "Grant pulse executed")

    redis = get_redis_client()
    keys = redis.keys("grants_composed:*")

    by_type = {}
    for key in keys:
        raw = redis.get(key)
        if raw:
            data = json.loads(raw)
            t = data.get("grant_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

    click.echo("📊 Grant Composition Pulse:")
    for grant_type, count in by_type.items():
        click.echo(f"- {grant_type.upper()}: {count}")
