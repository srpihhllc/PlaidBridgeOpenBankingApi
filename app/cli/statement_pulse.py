# app/cli/statement_pulse.py

import json

import click

from app.telemetry.ttl_emit import trace_log
from app.utils.redis_utils import get_redis_client


@click.command("cockpit:statement-pulse")
def statement_pulse():
    """Track live Redis-based bank statement generation stats."""
    # Emit cockpit telemetry
    trace_log("cli/statement_pulse/status", "Statement pulse emitted")

    redis = get_redis_client()
    keys = redis.keys("bank_statement:*")

    stats = {}
    for key in keys:
        raw = redis.get(key)
        if raw:
            data = json.loads(raw)
            bank = data.get("bank", "unknown")
            stats[bank] = stats.get(bank, 0) + 1

    click.echo("📊 Bank Statement Pulse:")
    for bank, count in stats.items():
        click.echo(f"- {bank}: {count}")
