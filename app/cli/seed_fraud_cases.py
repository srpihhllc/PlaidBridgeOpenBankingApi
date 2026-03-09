# FILE: app/cli/seed_fraud_cases.py

import random

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Transaction


@click.command("seed-fraud-cases")
@with_appcontext
def seed_fraud_cases():
    """Flag a handful of transactions as fraud."""

    click.echo("⚠️ Seeding fraud cases...")

    txns = Transaction.query.order_by(Transaction.id.desc()).limit(20).all()
    if not txns:
        click.echo("❌ No transactions found. Seed transactions first.")
        return

    fraud_samples = random.sample(txns, min(5, len(txns)))

    for txn in fraud_samples:
        txn.is_flagged = True
        txn.fraud_reason = random.choice(
            [
                "Unusual location",
                "High-risk merchant",
                "Velocity anomaly",
                "Card-not-present pattern",
            ]
        )

    db.session.commit()
    click.echo("✅ Fraud cases seeded.")
