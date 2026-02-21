# FILE: app/cli/reset_and_reseed.py

from subprocess import call

import click
from flask.cli import with_appcontext

from app.extensions import db


@click.command("reset-and-reseed")
@with_appcontext
def reset_and_reseed():
    """Reset the database and reseed all users."""

    click.echo("⚠️  WARNING: This will DROP ALL TABLES and recreate them.")
    if not click.confirm("Continue?"):
        click.echo("Cancelled.")
        return

    click.echo("🧨 Dropping all tables...")
    db.drop_all()

    click.echo("🛠️  Creating tables...")
    db.create_all()

    click.echo("🌱 Seeding admin, subscriber, and lender...")
    call(["flask", "seed-admin"])
    call(["flask", "seed-subscriber"])
    call(["flask", "seed-lender"])

    click.echo("\n📊 Cockpit‑Grade Seeding Report")
    click.echo("--------------------------------")
    click.echo("Admin:      admin@example.com / AdminPass123!")
    click.echo("Subscriber: subscriber@example.com / Test1234!")
    click.echo("Lender:     lender@example.com / LenderPass123!")
    click.echo("--------------------------------")
    click.echo("🎉 Environment reset and reseeded successfully.")
