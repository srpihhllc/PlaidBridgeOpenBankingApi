# app/cli/statement_leaders.py

import click

from app.telemetry.ttl_emit import trace_log


@click.command("cockpit:statement-leaders")
def statement_leaders():
    """List cockpit statement leaders."""
    # Emit cockpit telemetry
    trace_log("cli/statement_leaders/status", "Statement leaders listed")

    # TODO: replace with real leaders-fetching logic
    click.echo("📊 Leaders listed")
