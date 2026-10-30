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
def reset_and_reseed(ctx: click.Context) -> None:
    """Drop and recreate the database, then run the seed commands."""

    click.echo("⚠️  WARNING: This will DROP ALL TABLES and recreate them.")
    if not click.confirm("Continue?"):
        click.echo("Cancelled.")
        return

    click.echo("🧨 Dropping all tables...")
    db.drop_all()

    click.echo("🛠️  Creating tables...")
    db.create_all()

    # Walk up the Click context tree to find the Flask CLI command registry.
    root_ctx = ctx.find_root()
    root_command = root_ctx.command
    commands = getattr(root_command, "commands", None)

    if not isinstance(commands, dict):
        raise click.ClickException(
            "Could not access the root CLI command registry."
        )

    def run_seeder(name: str) -> None:
        command = commands.get(name)
        if command is None:
            raise click.ClickException(
                f"Could not find required command '{name}' in registry."
            )

        click.echo(f"🌱 Invoking: {name}")
        ctx.invoke(command)

    run_seeder("seed-admin")
    run_seeder("seed-subscriber")
    run_seeder("seed-lender")

    click.echo("\n📊 Cockpit-Grade Seeding Report Complete.")