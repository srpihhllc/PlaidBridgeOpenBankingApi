# =============================================================================
# FILE: app/cli/seed_mock_bank_transfers_all.py
# DESCRIPTION: Seed mock transfers for ALL subscribers.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.models import User
from app.services.bank_transaction_generator import seed_mock_bank_transfers_for_user


@click.command("seed-mock-bank-transfers-all")
@click.option("--count", default=10, help="Transfers per subscriber.")
@with_appcontext
def seed_mock_bank_transfers_all(count):
    """Seed mock ACH/Wire/Internal transfers for ALL subscribers."""

    click.echo("🏦 Seeding mock transfers for all subscribers...")

    subscribers = User.query.filter_by(role="subscriber").all()
    if not subscribers:
        click.echo("❌ No subscribers found.")
        return

    total = 0
    for user in subscribers:
        created = seed_mock_bank_transfers_for_user(user, count=count)
        total += created
        click.echo(f"   • {user.email}: {created} transfers")

    click.echo(f"✅ Completed. Total transfers seeded: {total}.")
