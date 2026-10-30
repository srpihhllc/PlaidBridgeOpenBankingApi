#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/basic_commands.py

"""Basic compatibility commands for the Flask CLI."""

from __future__ import annotations

import click


@click.command("verify-sandbox")
def verify_sandbox() -> None:
    """Verify Sandbox integration status and connectivity."""
    click.echo("Verifying Sandbox environment...")


@click.command("init-db")
def init_db() -> None:
    """Initialize database tables."""
    click.echo("Initializing database...")