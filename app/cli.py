#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli.py

import click
from flask import Flask


def register_cli_commands(app: Flask) -> None:
    """Register custom CLI commands with the Flask application."""

    @app.cli.command("verify-sandbox")
    def verify_sandbox() -> None:
        """Verify Sandbox integration status and connectivity."""
        click.echo("Verifying Sandbox environment...")

    @app.cli.command("init-db")
    def init_db() -> None:
        """Initialize database tables."""
        click.echo("Initializing database...")

