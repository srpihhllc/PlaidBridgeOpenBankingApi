# FILE: app/cli/seed_lender.py

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import BankAccount, BankInstitution, Lender, User


@click.command("seed-lender")
@click.option("--email", default=None, help="Lender email")
@click.option("--password", default=None, help="Lender password")
@click.option("--username", default=None, help="Lender username")
@click.option("--interactive", is_flag=True, help="Prompt for fields")
@with_appcontext
def seed_lender(email, password, username, interactive):
    """Create or update a lender user with sandbox-safe mock data."""

    default_email = "lender@example.com"
    default_password = "LenderPass123!"
    default_username = "lender_user"

    if interactive:
        email = email or click.prompt("Lender email")
        password = password or click.prompt(
            "Lender password", hide_input=True, confirmation_prompt=True
        )
        username = username or click.prompt("Lender username")
    else:
        email = email or default_email
        password = password or default_password
        username = username or default_username

    user = User.query.filter_by(email=email).first()

    if user:
        click.echo(f"Updating existing lender: {email}")
        user.password_hash = generate_password_hash(password)
        user.role = "lender"
        user.is_admin = False
        user.is_approved = True
        user.is_mfa_enabled = False

    else:
        click.echo(f"Creating new lender: {email}")
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="lender",
            is_admin=False,
            is_approved=True,
            is_mfa_enabled=False,
        )
        db.session.add(user)
        db.session.flush()

        # Create lender profile using actual model fields
        lender = Lender(
            user_id=user.id,
            business_name="Example Lending LLC",
            owner_name="Example Owner",
            ssn_or_ein="12-3456789",
            license_number="LIC-12345",
            address="123 Example Street",
            institution_name="Sandbox Lender Bank",
            verification_status="pending",
            verification_score=0,
            bank_linked=False,
        )
        db.session.add(lender)

        # Mock bank + account
        institution = BankInstitution(
            user_id=user.id,
            name="Sandbox Lender Bank",
            institution_id="sandbox-lender-001",
        )
        account = BankAccount(
            user_id=user.id,
            account_type="checking",
            account_number="999888777",
            balance=5000.00,
        )
        db.session.add_all([institution, account])

    db.session.commit()
    click.echo("✅ Lender user seeded successfully.")
