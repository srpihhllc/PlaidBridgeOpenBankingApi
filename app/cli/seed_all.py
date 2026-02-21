# FILE: app/cli/seed_all.py

from subprocess import call

import click
from flask.cli import with_appcontext


@click.command("seed-all")
@with_appcontext
def seed_all():
    """Seed admin, subscriber, and lender users in one sweep."""

    click.echo("🚀 Seeding ALL users...")

    call(["flask", "seed-admin"])
    call(["flask", "seed-subscriber"])
    call(["flask", "seed-lender"])

    click.echo("✅ All users seeded successfully.")
