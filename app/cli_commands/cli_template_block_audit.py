# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/cli_template_block_audit.py

import click
import redis
from flask import current_app

from app.utils.template_block_audit import audit_template_blocks


@click.command("template_block_audit")
def template_block_audit_command():
    """
    Run the cockpit-grade template block audit.
    """
    try:
        redis_client = redis.Redis.from_url(
            current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        )
    except Exception:
        redis_client = None

    summary = audit_template_blocks(redis_client)

    click.echo("✅ Template block audit complete.")
    click.echo("------------------------------------------------------------")
    click.echo(f"Templates scanned:              {summary['templates_scanned']}")
    click.echo(f"Block definitions found:        {summary['block_definitions']}")
    click.echo(f"Missing required blocks:        {summary['missing_required_blocks']}")
    click.echo(f"Cross-domain block violations:  {summary['cross_domain_block_violations']}")
    click.echo(f"Errors detected:                {summary['errors']}")
    click.echo("------------------------------------------------------------")
    click.echo("Check logs and cockpit telemetry for detailed results.")
