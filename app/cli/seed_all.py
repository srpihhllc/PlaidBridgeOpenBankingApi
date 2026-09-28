# FILE: app/cli/seed_all.py

from subprocess import CalledProcessError, check_call

import click
from flask.cli import with_appcontext


@click.command("seed-all")
@with_appcontext
def seed_all():
    """Seed admin, subscriber, and lender users in one sweep."""

    click.echo("🚀 Seeding identity core (Admin, Subscriber, Lender)...")

    commands = [
        ["flask", "seed-admin"],
        ["flask", "seed-subscriber"],
        ["flask", "seed-lender"],
    ]

    for cmd in commands:
        try:
            check_call(cmd)
        except CalledProcessError as exc:
            raise click.ClickException(
                f"❌ Identity seeding halted on command '{' '.join(cmd)}' (Exit code: {exc.returncode})."
            )

    click.echo("\n📊 Cockpit-Grade Identity Seeding Summary")
    click.echo("--------------------------------")
    click.echo("✅ Admin identity verified and established.")
    click.echo("✅ Subscriber identity verified and established.")
    click.echo("✅ Lender identity verified and established.")
    click.echo("--------------------------------")
    click.echo("🎉 Core user identities seeded successfully.")
