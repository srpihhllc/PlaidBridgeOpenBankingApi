# =============================================================================
# FILE: app/cli_commands/cli_template_block_audit.py
# DESCRIPTION: CLI command to audit template block integrity.
#              Hardened for context-safety and runtime resiliency.
# =============================================================================

import click
import redis
from flask import current_app
from flask.cli import (
    with_appcontext,
)  # ✅ Required for context stack resolution

from app.utils.template_block_audit import audit_template_blocks


@click.command("template_block_audit")
@with_appcontext  # ✅ Pins the active thread to the Flask application context
def template_block_audit_command():
    """
    Run the cockpit-grade template block audit.
    """
    # 1. Defensively resolve Redis client
    try:
        redis_client = redis.Redis.from_url(
            current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        )
    except Exception as e:
        click.echo(
            f"⚠️ Redis connection failed, falling back to local-only audit: {e}",
            err=True,
        )
        redis_client = None

    # 2. Execute audit with error isolation
    try:
        summary = audit_template_blocks(redis_client)
    except Exception as e:
        click.echo(
            f"❌ Template block audit encountered a fatal error: {e}", err=True
        )
        return

    # 3. Defensive reporting (ensuring keys exist before access)
    click.echo("✅ Template block audit complete.")
    click.echo("------------------------------------------------------------")
    click.echo(
        f"Templates scanned:             {summary.get('templates_scanned', 0)}"
    )
    click.echo(
        f"Block definitions found:       {summary.get('block_definitions', 0)}"
    )
    click.echo(
        f"Missing required blocks:       {summary.get('missing_required_blocks', 0)}"
    )
    click.echo(
        f"Cross-domain block violations: {summary.get('cross_domain_block_violations', 0)}"
    )
    click.echo(f"Errors detected:               {summary.get('errors', 0)}")
    click.echo("------------------------------------------------------------")
    click.echo("Check logs and cockpit telemetry for detailed results.")
