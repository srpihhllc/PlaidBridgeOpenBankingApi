# =============================================================================
# FILE: /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/cli_template_inheritance.py
# DESCRIPTION: CLI command to audit template inheritance tree hierarchies.
#              Uses @with_appcontext to prevent Werkzeug thread-local context leaks.
# =============================================================================

import click
import redis
from flask import current_app
from flask.cli import with_appcontext  # ✅ Required for LocalProxy stack resolution

from app.utils.template_inheritance_audit import audit_template_inheritance


@click.command("template_inheritance")
@with_appcontext  # ✅ Pins the active thread to the Flask application context factory
def template_inheritance_command():
    """
    Run the cockpit-grade template inheritance audit.
    """
    try:
        # Resolves cleanly now because current_app is safely bound
        redis_client = redis.Redis.from_url(
            current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        )
    except Exception:
        redis_client = None

    try:
        summary = audit_template_inheritance(redis_client)
    except Exception as e:
        current_app.logger.error(f"[template_inheritance] Tree traversal failed: {e}")
        click.echo(f"❌ Inheritance compilation failed: {e}")
        return

    click.echo("✅ Template inheritance audit complete.")
    click.echo("------------------------------------------------------------")
    click.echo(f"Templates scanned:        {summary.get('templates_scanned', 0)}")
    click.echo(f"Inheritance links:        {summary.get('inheritance_links', 0)}")
    click.echo(f"Missing parents:          {summary.get('missing_parents', 0)}")
    click.echo(f"Cross-domain violations:  {summary.get('cross_domain_violations', 0)}")
    click.echo(f"Circular inheritance:     {summary.get('circular_inheritance', 0)}")
    click.echo(f"Errors detected:          {summary.get('errors', 0)}")
    click.echo("------------------------------------------------------------")
    click.echo("Check logs and cockpit telemetry for detailed results.")