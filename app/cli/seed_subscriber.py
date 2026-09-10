# =============================================================================
# FILE: app/cli/seed_subscriber.py
# DESCRIPTION: Production-aligned seeder matching route authentication schema.
# =============================================================================

import os
import sys

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    BankAccount,
    BankInstitution,
    SubscriberProfile,
    User,
    UserDashboard,
)


@click.command("seed-subscriber")
@click.option("--email", default=None, help="Subscriber email")
@click.option("--password", default=None, help="Subscriber password")
@click.option("--username", default=None, help="Subscriber username")
@click.option("--interactive", is_flag=True, help="Prompt for fields")
@with_appcontext
def seed_subscriber(email, password, username, interactive):
    """Create a fully populated subscriber matching application registration requirements."""

    if interactive:
        email = email or click.prompt("Subscriber email")
        password = password or click.prompt(
            "Subscriber password", hide_input=True, confirmation_prompt=True
        )
        username = username or click.prompt("Subscriber username")
    else:
        email = email or os.environ.get("USER_EMAIL")
        password = password or os.environ.get("USER_PASSWORD")
        username = username or os.environ.get(
            "USER_USERNAME", "subscriber_user"
        )

    if not email or not password:
        click.echo(
            "❌ ERROR: USER_EMAIL and USER_PASSWORD must be set in the environment."
        )
        sys.exit(1)

    # Gather data mappings aligned directly with your registration route requirements
    ssn_last4 = os.environ.get("USER_SSN_LAST4", "2223")
    primary_phone = os.environ.get("USER_PRIMARY_PHONE", "901-555-0199")
    bank_name = os.environ.get("USER_BANK_NAME", "Demo Bank")
    routing_number = os.environ.get("USER_ROUTING_NUMBER", "123456789")
    account_ending = os.environ.get("USER_ACCOUNT_ENDING", "2223")

    business_address = os.environ.get(
        "USER_BUSINESS_ADDRESS", "123 Innovation Way"
    )
    business_city = os.environ.get("USER_BUSINESS_CITY", "Memphis")
    business_state = os.environ.get("USER_BUSINESS_STATE", "TN")
    business_zip = os.environ.get("USER_BUSINESS_ZIP", "38103")
    business_phone = os.environ.get("USER_BUSINESS_PHONE", "901-555-0200")
    ein = os.environ.get("USER_EIN", "12-3456789")
    home_address = os.environ.get("USER_HOME_ADDRESS", "456 Residential Ln")

    user = User.query.filter_by(email=email).first()

    if user:
        click.echo(
            f"ℹ️ Updating and synchronizing existing subscriber: {email}"
        )
        user.set_password(password)  # Using matching model helper from route
        user.role = "subscriber"
        user.is_admin = False
        user.is_approved = True
        user.mfa_pending_setup = True

        # Sync profile fields down to table context
        user.ssn_last4 = ssn_last4
        user.primary_phone = primary_phone
        user.bank_name = bank_name
        user.routing_number = routing_number
        user.account_ending = account_ending
        user.business_address = business_address
        user.business_city = business_city
        user.business_state = business_state
        user.business_zip = business_zip
        user.business_phone = business_phone
        user.ein = ein
        user.home_address = home_address
    else:
        click.echo(
            f"🌱 Creating pristine registration-compliant subscriber: {email}"
        )
        user = User(
            username=username,
            email=email,
            role="subscriber",
            is_admin=False,
            is_approved=True,
            mfa_pending_setup=True,  # Aligned with default route security state
            ssn_last4=ssn_last4,
            primary_phone=primary_phone,
            bank_name=bank_name,
            routing_number=routing_number,
            account_ending=account_ending,
            business_address=business_address,
            business_city=business_city,
            business_state=business_state,
            business_zip=business_zip,
            business_phone=business_phone,
            ein=ein,
            home_address=home_address,
            home_same_as_business=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # ---------------------------------------------------------------------
        # Downstream Ecosystem Hydration
        # ---------------------------------------------------------------------
        dashboard = UserDashboard(user_id=user.id)

        profile = SubscriberProfile(user_id=user.id)
        profile.generate_api_key()

        institution = BankInstitution.query.filter_by(
            institution_id="demo-bank-001"
        ).first()
        if not institution:
            institution = BankInstitution(
                user_id=user.id, name=bank_name, institution_id="demo-bank-001"
            )

        account = BankAccount.query.filter_by(
            account_number="0001112223"
        ).first()
        if not account:
            account = BankAccount(
                user_id=user.id,
                account_type="checking",
                account_number="0001112223",
                balance=100.00,
            )

        db.session.add_all([dashboard, profile, institution, account])

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        # Concurrency verification fallback
        user = User.query.filter_by(email=email).first()

        if not SubscriberProfile.query.filter_by(user_id=user.id).first():
            p = SubscriberProfile(user_id=user.id)
            p.generate_api_key()
            db.session.add(p)

        if not UserDashboard.query.filter_by(user_id=user.id).first():
            db.session.add(UserDashboard(user_id=user.id))

        if not BankInstitution.query.filter_by(
            institution_id="demo-bank-001"
        ).first():
            db.session.add(
                BankInstitution(
                    user_id=user.id,
                    name=bank_name,
                    institution_id="demo-bank-001",
                )
            )

        if not BankAccount.query.filter_by(
            account_number="0001112223"
        ).first():
            db.session.add(
                BankAccount(
                    user_id=user.id,
                    account_type="checking",
                    account_number="0001112223",
                    balance=100.00,
                )
            )
        db.session.commit()

    click.echo("✅ Subscriber user context fully synchronized and seeded.")


# -----------------------------------------------------------------------------
# Plural Command Alias
# -----------------------------------------------------------------------------
@click.command("seed-subscribers")
@click.option("--email", default=None, help="Subscriber email")
@click.option("--password", default=None, help="Subscriber password")
@click.option("--username", default=None, help="Subscriber username")
@click.option("--interactive", is_flag=True, help="Prompt for fields")
@click.pass_context
def seed_subscribers(ctx, email, password, username, interactive):
    """Alias for seed-subscriber."""
    ctx.forward(seed_subscriber)
