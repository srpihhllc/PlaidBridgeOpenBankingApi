# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/sweep_endpoints.py

# =============================================================================
# FILE: app/cli_commands/sweep_endpoints.py
# DESCRIPTION: CLI command to list all registered Flask endpoints and routes.
# =============================================================================

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("sweep-endpoints")
@with_appcontext
def sweep_endpoints():
    """List all registered Flask endpoints and their URL rules."""
    rules = sorted(current_app.url_map.iter_rules(), key=lambda r: r.endpoint)
    for rule in rules:
        click.echo(f"{rule.endpoint:30} → {rule}")
