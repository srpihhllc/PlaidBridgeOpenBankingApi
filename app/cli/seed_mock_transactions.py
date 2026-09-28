# FILE: app/cli/seed_mock_transactions.py

import os

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import BankAccount, Transaction, User
from app.services.merchant_generator import generate_plaid_style_transaction


@click.command("seed-mock-transactions")
@with_appcontext
def seed_mock_transactions():
    """Seed realistic, Plaid-style enriched mock transactions for the subscriber."""

    click.echo("📄 Seeding mock transactions...")

    target_email = os.environ.get("USER_EMAIL", "subscriber@example.com")
    user = User.query.filter_by(email=target_email).first() or User.query.filter_by(role="subscriber").first()

    if not user:
        raise click.ClickException("❌ Subscriber not found. Seed subscriber first.")

    account = BankAccount.query.filter_by(user_id=user.id).first()
    if not account:
        raise click.ClickException("❌ Subscriber has no bank account.")

    for _ in range(40):
        data = generate_plaid_style_transaction()

        txn = Transaction(
            user_id=user.id,
            account_id=account.id,
            amount=data["amount"],
            description=data["description"],
            category=data["category"],
            date=data["date"],
            is_pending=data["is_pending"],
            mcc=data["mcc"],
            fraud_score=data["fraud_score"],
            cluster=data["cluster"],
            category_hierarchy=data["category_hierarchy"],
            location=data["location"],
            payment_meta=data["payment_meta"],
        )

        db.session.add(txn)

    db.session.commit()
    click.echo("✅ Mock transactions seeded.")