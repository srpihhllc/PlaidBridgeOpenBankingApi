# FILE: app/cli/seed_subscriber.py

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import BankAccount, BankInstitution, SubscriberProfile, User, UserDashboard


@click.command("seed-subscriber")
@click.option("--email", default=None, help="Subscriber email")
@click.option("--password", default=None, help="Subscriber password")
@click.option("--username", default=None, help="Subscriber username")
@click.option("--interactive", is_flag=True, help="Prompt for fields")
@with_appcontext
def seed_subscriber(email, password, username, interactive):
    """Create a fully hydrated subscriber user."""

    default_email = "subscriber@example.com"
    default_password = "Test1234!"
    default_username = "subscriber_user"

    if interactive:
        email = email or click.prompt("Subscriber email")
        password = password or click.prompt(
            "Subscriber password", hide_input=True, confirmation_prompt=True
        )
        username = username or click.prompt("Subscriber username")
    else:
        email = email or default_email
        password = password or default_password
        username = username or default_username

    user = User.query.filter_by(email=email).first()

    if user:
        click.echo(f"Updating existing subscriber: {email}")
        user.password_hash = generate_password_hash(password)
        user.is_admin = False
        user.role = "subscriber"
        user.is_approved = True
        user.is_mfa_enabled = False
    else:
        click.echo(f"Creating new subscriber: {email}")
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=False,
            role="subscriber",
            is_approved=True,
            is_mfa_enabled=False,
        )
        db.session.add(user)
        db.session.flush()

        # ---------------------------------------------------------------------
        # Cockpit‑grade hydration of subscriber ecosystem
        # ---------------------------------------------------------------------
        dashboard = UserDashboard(user_id=user.id)

        # ⭐ Corrected Seeder Block (drop‑in replacement)
        profile = SubscriberProfile(user_id=user.id)
        profile.generate_api_key()

        institution = BankInstitution(
            user_id=user.id, name="Demo Bank", institution_id="demo-bank-001"
        )

        account = BankAccount(
            user_id=user.id,
            account_type="checking",
            account_number="0001112223",
            balance=100.00,
        )

        db.session.add_all([dashboard, profile, institution, account])

    db.session.commit()
    click.echo("✅ Subscriber user seeded successfully.")
