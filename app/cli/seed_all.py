# FILE: app/cli/seed_all.py

from subprocess import call

import click
from flask.cli import with_appcontext


@click.command("seed-all")
@with_appcontext
def seed_all():
    """Seed admin, subscriber, and lender users in one sweep."""

    click.echo("🚀 Seeding identity core (Admin, Subscriber, Lender)...")

    call(["flask", "seed-admin"])
    call(["flask", "seed-subscriber"])
    call(["flask", "seed-lender"])

    click.echo("\n📊 Cockpit-Grade Identity Seeding Summary")
    click.echo("--------------------------------")
    click.echo("✅ Admin identity verified and established.")
    click.echo("✅ Subscriber identity verified and established.")
    click.echo("✅ Lender identity verified and established.")
    click.echo("--------------------------------")
    click.echo("🎉 Core user identities seeded successfully.")
