# app/cli_commands/diagnostics_cli.py

import json
import os
import time

import click
from flask import current_app
from werkzeug.wrappers import Response

from app.blueprints.diagnostics import get_full_diagnostics


@click.command("diagnostics-full")
@click.option("--watch", is_flag=True, help="Refresh diagnostics every 5 seconds.")
def diagnostics_full(watch):
    """
    Run the unified diagnostics check from CLI.
    Use --watch to monitor live system changes.

    This command bypasses web-auth guards using DIAGNOSTICS_CLI_MODE.
    """

    def run_check():
        """Helper to execute the diagnostics logic within the correct contexts."""
        with current_app.app_context():
            # 🟢 ACTIVATE BYPASS: Signal to diagnostics.py that we are a trusted CLI process
            current_app.config["DIAGNOSTICS_CLI_MODE"] = True

            try:
                # Provide a fake request context so blueprint logic (request/url_for) doesn't crash
                with current_app.test_request_context("/__cli_diagnostics__"):
                    result = get_full_diagnostics()

                # Normalize Flask response formats: (dict, status) or Response objects
                if isinstance(result, tuple):
                    response_body, _ = result
                else:
                    response_body = result

                # Extract raw data from Response objects or serialize dicts
                if isinstance(response_body, Response):
                    raw = response_body.get_data(as_text=True)
                else:
                    raw = json.dumps(response_body, indent=2)

                return json.loads(raw)

            except Exception as exc:
                return {
                    "error": "Diagnostics CLI failure",
                    "message": str(exc),
                    "type": exc.__class__.__name__,
                }

    # --- EXECUTION LOGIC ---

    if watch:
        click.secho(
            "🛰️  Starting Neural Pulse Watcher... (Ctrl+C to stop)",
            fg="yellow",
            bold=True,
        )
        try:
            while True:
                data = run_check()

                # Clear terminal screen for the "Dashboard" look
                os.system("clear" if os.name != "nt" else "cls")

                timestamp = time.strftime("%H:%M:%S")
                click.secho(f"--- LIVE PULSE | {timestamp} ---", fg="cyan", bold=True)

                # Output the JSON
                click.echo(json.dumps(data, indent=2))

                # 🚨 Visual Alert if DB goes offline during watch
                db_status = data.get("infra", {}).get("database", {}).get("online", True)
                if not db_status:
                    click.secho(
                        "\n🚨 CRITICAL: DATABASE OFFLINE",
                        fg="red",
                        bold=True,
                        blink=True,
                    )

                time.sleep(5)
        except KeyboardInterrupt:
            click.echo("\nWatcher stopped.")
    else:
        # Standard one-time execution
        data = run_check()
        click.echo(json.dumps(data, indent=2))
