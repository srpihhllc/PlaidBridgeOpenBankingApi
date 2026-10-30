# =============================================================================
# FILE: app/cli/seed_mock_bank_transfers_summary.py
# DESCRIPTION: CLI command to seed mock transfers and report the result.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.models import User
from app.services.bank_transaction_generator import (
    seed_mock_bank_transfers_for_user,
)


@click.command("seed-mock-bank-transfers-summary")
@with_appcontext
def seed_mock_bank_transfers_summary() -> None:
    """Seed mock transfers for the subscriber and print a count summary."""
    click.echo("🏦 Seeding mock bank transfers...")

    user = User.query.filter_by(email="subscriber@example.com").first()
    if user is None:
        click.echo("❌ Subscriber not found. Seed the subscriber first.")
        return

    count = seed_mock_bank_transfers_for_user(user, count=25)

    click.echo(f"✅ Seeded {count} mock bank transfers.")