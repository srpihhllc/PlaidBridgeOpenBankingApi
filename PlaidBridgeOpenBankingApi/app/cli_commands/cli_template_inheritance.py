# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/cli_template_inheritance.py

import click
import redis
from flask import current_app

from app.utils.template_inheritance_audit import audit_template_inheritance


@click.command("template_inheritance")
def template_inheritance_command():
    """
    Run the cockpit-grade template inheritance audit.
    """
    try:
        redis_client = redis.Redis.from_url(
            current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        )
    except Exception:
        redis_client = None

    summary = audit_template_inheritance(redis_client)

    click.echo("✅ Template inheritance audit complete.")
    click.echo("------------------------------------------------------------")
    click.echo(f"Templates scanned:        {summary['templates_scanned']}")
    click.echo(f"Inheritance links:        {summary['inheritance_links']}")
    click.echo(f"Missing parents:          {summary['missing_parents']}")
    click.echo(f"Cross-domain violations:  {summary['cross_domain_violations']}")
    click.echo(f"Circular inheritance:     {summary['circular_inheritance']}")
    click.echo(f"Errors detected:          {summary['errors']}")
    click.echo("------------------------------------------------------------")
    click.echo("Check logs and cockpit telemetry for detailed results.")
