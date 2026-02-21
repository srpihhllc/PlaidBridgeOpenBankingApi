# =============================================================================
# FILE: app/cli/seed_mock_bank_transfers_summary.py
# DESCRIPTION: CLI command to display a summary table of mock transfers.
# =============================================================================

from typing import Any

import click
from flask.cli import with_appcontext

from app.models import User
from app.services.bank_transaction_generator import seed_mock_bank_transfers_for_user

# Optional import: tabulate (with safe fallback)
try:
    from tabulate import tabulate  # type: ignore[import-untyped]
except Exception:
    tabulate = None  # type: ignore[assignment]


@click.command("seed-mock-bank-transfers-summary")
@with_appcontext
def seed_mock_bank_transfers_summary() -> None:
    """
    Seed mock transfers and print a summary table.
    Safe even if 'tabulate' is not installed.
    """

    click.echo("🏦 Seeding mock bank transfers (summary mode)...")

    user = User.query.filter_by(email="subscriber@example.com").first()
    if not user:
        click.echo("❌ Subscriber not found. Seed subscriber first.")
        return

    transfers: list[dict[str, Any]] = seed_mock_bank_transfers_for_user(
        user, count=25, return_transfers=True
    )

    click.echo(f"✅ Seeded {len(transfers)} mock bank transfers.\n")

    if not transfers:
        click.echo("No transfers generated.")
        return

    # If tabulate is available, use it. Otherwise fallback to plain text.
    if tabulate:
        table = tabulate(
            [
                [
                    t.get("id"),
                    t.get("type"),
                    t.get("amount"),
                    t.get("status"),
                    t.get("created_at"),
                ]
                for t in transfers
            ],
            headers=["ID", "Type", "Amount", "Status", "Created At"],
            tablefmt="github",
        )
        click.echo(table)
    else:
        click.echo("⚠️ 'tabulate' not installed. Showing plain-text summary:\n")
        for t in transfers:
            click.echo(
                f"- ID={t.get('id')} | {t.get('type')} | ${t.get('amount')} | "
                f"{t.get('status')} | {t.get('created_at')}"
            )
