# =============================================================================
# FILE: app/cli/reset_and_reseed.py
# DESCRIPTION: Programmatic orchestration layer executing in-process migrations.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.extensions import db


@click.command("reset-and-reseed")
@click.pass_context
@with_appcontext
def reset_and_reseed(ctx: click.Context):
    """Purges all structural entities and hydrates identity targets atomically."""

    click.echo("⚠️  WARNING: This will DROP ALL TABLES and recreate them.")
    if not click.confirm("Continue?"):
        click.echo("Cancelled.")
        return

    click.echo("🧨 Dropping all tables...")
    db.drop_all()

    click.echo("🛠️  Creating tables...")
    db.create_all()

    # Access the command registry from the root CLI (manage.py)
    # The 'ctx.parent' refers to the FlaskGroup 'cli'
    commands = ctx.parent.command.commands

    # Helper to invoke safely
    def run_seeder(name: str):
        if name in commands:
            click.echo(f"🌱 Invoking: {name}")
            ctx.invoke(commands[name])
        else:
            click.echo(
                f"❌ FATAL: Could not find command '{name}' in registry."
            )

    # Execute seeders in-process
    run_seeder("seed-admin")
    run_seeder("seed-subscriber")
    run_seeder("seed-lender")

    click.echo("\n📊 Cockpit-Grade Seeding Report Complete.")
