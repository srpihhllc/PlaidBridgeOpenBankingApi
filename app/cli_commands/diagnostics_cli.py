# =============================================================================
# FILE: app/cli_commands/diagnostics_cli.py
# DESCRIPTION: Hardened CLI command layer executing system diagnostics checks.
# =============================================================================

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.wrappers import Response

from app.blueprints.diagnostics import get_full_diagnostics


@click.command("diagnostics-full")
@click.option("--watch", is_flag=True, help="Refresh diagnostics every 5 seconds continuously.")
@with_appcontext
def diagnostics_full(watch: bool) -> None:
    """
    Run the unified diagnostics health check engine from the CLI context.
    """

    def _execute_isolated_diagnostic() -> dict[str, Any]:
        """Executes the diagnostic pipeline within the established app context."""
        
        # Cache the original state to guarantee zero permanent pollution
        original_mode = current_app.config.get("DIAGNOSTICS_CLI_MODE", False)
        current_app.config["DIAGNOSTICS_CLI_MODE"] = True

        try:
            # Provision a mock request block for internal dependencies
            with current_app.test_request_context("/__cli_diagnostics__"):
                result = get_full_diagnostics()

            if isinstance(result, tuple):
                response_body, _ = result
            else:
                response_body = result

            if isinstance(response_body, Response):
                return json.loads(response_body.get_data(as_text=True))
            elif isinstance(response_body, dict):
                return response_body
            else:
                return {"data": str(response_body)}

        except Exception as exc:
            current_app.logger.exception("Diagnostics CLI pipeline failure.")
            return {
                "error": "Diagnostics CLI failure",
                "message": str(exc),
                "type": exc.__class__.__name__,
            }
        finally:
            current_app.config["DIAGNOSTICS_CLI_MODE"] = original_mode

    # --- CLI RUNTIME EXECUTION GATEWAY ---
    if not watch:
        data = _execute_isolated_diagnostic()
        click.echo(json.dumps(data, indent=2))
        return

    # Continuous Watch loop orchestration
    click.secho("🛰️ Starting Neural Pulse Watcher... (Ctrl+C to stop)", fg="yellow", bold=True)
    try:
        while True:
            data = _execute_isolated_diagnostic()
            sys.stdout.write("\033[H\033[2J")
            sys.stdout.flush()
            
            timestamp = time.strftime("%H:%M:%S")
            click.secho(f"--- LIVE PULSE | {timestamp} ---", fg="cyan", bold=True)
            click.echo(json.dumps(data, indent=2))
            
            # Simple health check alert
            infra_map = data.get("infra", {})
            if isinstance(infra_map, dict):
                db_map = infra_map.get("database", {})
                if isinstance(db_map, dict) and not db_map.get("online", True):
                    click.secho("\n🚨 CRITICAL ERROR: DB OFFLINE", fg="red", bold=True, blink=True)

            time.sleep(5)
    except KeyboardInterrupt:
        click.echo("\nWatcher gracefully disengaged.")


@click.command("mail-debug")
@with_appcontext
def mail_debug():
    """Inspects currently loaded Mail configurations vs OS environment."""
    click.echo("--- Mail Configuration Debug ---")
    keys = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME']
    
    for key in keys:
        config_val = current_app.config.get(key)
        env_val = os.environ.get(key, "NOT SET IN OS")
        
        if config_val is None and env_val == "NOT SET IN OS":
            status = "⚠️ MISSING"
        elif str(config_val) == str(env_val):
            status = "✅ MATCH"
        else:
            status = "❌ MISMATCH"
            
        click.echo(f"{key:15}: {config_val} (OS: {env_val}) [{status}]")