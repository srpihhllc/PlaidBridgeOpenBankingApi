# FILE: app/cli/seed_everything.py

from subprocess import call

import click
from flask.cli import with_appcontext


@click.command("seed-everything")
@with_appcontext
def seed_everything():
    """Run the full cockpit-grade mock data suite."""

    click.echo("🚀 Seeding FULL cockpit data suite...")

    call(["flask", "seed-admin"])
    call(["flask", "seed-subscriber"])
    call(["flask", "seed-lender"])
    call(["flask", "seed-mock-transactions"])
    call(["flask", "seed-fraud-cases"])
    call(["flask", "seed-timeline"])
    call(["flask", "seed-todos"])

    click.echo("🎉 FULL cockpit data suite seeded successfully.")
