# =============================================================================
# FILE: app/cli/seed_mock_bank_transfers_flags.py
# DESCRIPTION: CLI command with flags for email + count.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.models import User
from app.services.bank_transaction_generator import seed_mock_bank_transfers_for_user


@click.command("seed-mock-bank-transfers-flags")
@click.option("--email", required=True, help="Email of the subscriber.")
@click.option("--count", default=25, help="Number of transfers to seed.")
@with_appcontext
def seed_mock_bank_transfers_flags(email, count):
    """Seed mock ACH/Wire/Internal transfers for a specific subscriber."""

    click.echo(f"🏦 Seeding {count} mock transfers for {email}...")

    user = User.query.filter_by(email=email).first()
    if not user:
        click.echo("❌ User not found.")
        return

    created = seed_mock_bank_transfers_for_user(user, count=count)

    click.echo(f"✅ Seeded {created} mock bank transfers for {email}.")
