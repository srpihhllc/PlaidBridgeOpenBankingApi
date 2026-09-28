
import click

from flask import Flask



def register_cli_commands(app: Flask) -> None:

    """Register custom CLI commands with the Flask application instance."""

    

    @app.cli.command("verify-sandbox")

    def verify_sandbox():

        """Verify Sandbox integration status and connectivity."""

        click.echo("Verifying Sandbox environment...")



    @app.cli.command("init-db")

    def init_db():

        """Initialize database tables."""

        click.echo("Initializing database...")

