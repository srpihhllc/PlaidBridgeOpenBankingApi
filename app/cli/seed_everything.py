# FILE: app/cli/seed_everything.py

from subprocess import CalledProcessError, check_call

import click
from flask.cli import with_appcontext


@click.command("seed-everything")
@with_appcontext
def seed_everything():
    """Run the full cockpit-grade mock data suite."""

    click.echo("🚀 Seeding FULL cockpit data suite...")

    commands = [
        ["flask", "seed-admin"],
        ["flask", "seed-subscriber"],
        ["flask", "seed-lender"],
        ["flask", "seed-mock-transactions"],
        ["flask", "seed-fraud-cases"],
        ["flask", "seed-timeline"],
        ["flask", "seed-todos"],
    ]

    for cmd in commands:
        try:
            check_call(cmd)
        except CalledProcessError as exc:
            raise click.ClickException(
                f"❌ Seeding pipeline halted on command '{' '.join(cmd)}' (Exit code: {exc.returncode})."
            )

    click.echo("\n📊 Cockpit-Grade Full Suite Seeding Summary")
    click.echo("--------------------------------")
    click.echo("✅ Core user authentication vectors established.")
    click.echo("✅ Financial transaction histories populated.")
    click.echo("✅ Fraud mitigation tracking matrix initialized.")
    click.echo("✅ System activity timeline vectors synced.")
    click.echo("✅ Interactive user action items populated.")
    click.echo("--------------------------------")
    click.echo("🎉 FULL cockpit mock data suite seeded successfully.")