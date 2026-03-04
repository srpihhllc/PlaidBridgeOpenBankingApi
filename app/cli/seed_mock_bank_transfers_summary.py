# =============================================================================
# FILE: app/cli/seed_mock_bank_transfers_summary.py
# DESCRIPTION: Seed transfers and print a summary table.
# =============================================================================

import click
from flask.cli import with_appcontext
from tabulate import tabulate

from app.models import BankTransaction, User
from app.services.bank_transaction_generator import seed_mock_bank_transfers_for_user


@click.command("seed-mock-bank-transfers-summary")
@click.option("--email", required=True, help="Email of the subscriber.")
@click.option("--count", default=25, help="Number of transfers to seed.")
@with_appcontext
def seed_mock_bank_transfers_summary(email, count):
    """Seed transfers and print a summary table."""

    click.echo(f"🏦 Seeding {count} transfers for {email}...")

    user = User.query.filter_by(email=email).first()
    if not user:
        click.echo("❌ User not found.")
        return

    seed_mock_bank_transfers_for_user(user, count=count)

    # Fetch last N transfers
    txns = BankTransaction.query.order_by(BankTransaction.timestamp.desc()).limit(count).all()

    table = [
        [
            t.id,
            t.txn_type.upper(),
            f"${t.amount:.2f}",
            t.payment_channel,
            t.timestamp.strftime("%Y-%m-%d %H:%M"),
        ]
        for t in txns
    ]

    click.echo()
    click.echo(
        tabulate(
            table,
            headers=["ID", "Type", "Amount", "Channel", "Timestamp"],
            tablefmt="fancy_grid",
        )
    )
    click.echo()
    click.echo("✅ Transfers seeded and summary displayed.")
