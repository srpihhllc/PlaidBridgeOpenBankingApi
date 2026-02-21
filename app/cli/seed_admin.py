# FILE: app/cli/seed_admin.py

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import BankAccount, BankInstitution, SubscriberProfile, User, UserDashboard


@click.command("seed-admin")
@click.option("--email", default=None, help="Admin email address (omit to use default)")
@click.option("--password", default=None, help="Admin password (omit to use default)")
@click.option(
    "--interactive",
    is_flag=True,
    help="Prompt for email/password and create stub records",
)
@with_appcontext
def seed_admin(email, password, interactive):
    """Create or update the admin user."""

    # Safe example defaults
    default_username = "admin_user"
    default_email = "admin@example.com"
    default_password = "AdminPass123!"

    # Interactive mode
    if interactive:
        if not email:
            email = click.prompt("Admin email")
        if not password:
            password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)
    else:
        email = email or default_email
        password = password or default_password

    # Check if admin already exists
    user = User.query.filter_by(email=email).first()

    if user:
        click.echo(f"Updating existing admin user: {email}")
        user.password_hash = generate_password_hash(password)
        user.is_admin = True
        user.role = "admin"
        user.is_approved = True  # ⭐ REQUIRED FOR LOGIN
        user.is_mfa_enabled = False  # ⭐ PREVENT MFA BLOCK
    else:
        click.echo(f"Creating new admin user: {email}")
        user = User(
            username=default_username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True,
            role="admin",
            is_approved=True,  # ⭐ REQUIRED FOR LOGIN
            is_mfa_enabled=False,  # ⭐ PREVENT MFA BLOCK
        )
        db.session.add(user)
        db.session.flush()

        # Optional: create admin dashboard scaffolding
        if interactive:
            dashboard = UserDashboard(user_id=user.id)
            profile = SubscriberProfile(user_id=user.id, phone="", business_name="")
            institution = BankInstitution(
                user_id=user.id, name="Default Bank", institution_id="stub-bank-001"
            )
            account = BankAccount(
                user_id=user.id,
                account_type="checking",
                account_number="0000000000",
                balance=0.0,
            )
            db.session.add_all([dashboard, profile, institution, account])

    db.session.commit()
    click.echo("✅ Admin user seeded successfully.")
