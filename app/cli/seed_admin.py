# =============================================================================
# FILE: app/cli/seed_admin.py
# DESCRIPTION: End-to-end idempotent hydration for the canonical admin account.
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
    UserDashboard
)


# 🟢 CRITICAL FIX: Explicitly hyphenated to match Flask CLI and orchestration routing
@click.command("seed-admin")
@with_appcontext
def seed_admin():
    """Seed or synchronize the canonical administrator account using .env credentials."""
    
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    username = os.environ.get("ADMIN_USERNAME", "admin_user")

    # Strict enforcement of environment variables
    if not email or not password:
        click.echo("❌ ERROR: ADMIN_EMAIL and ADMIN_PASSWORD must be set in the environment.")
        sys.exit(1)

    # 1. Authoritative Identity Resolution
    user = User.query.filter_by(email=email).first()
    
    if user:
        click.echo(f"ℹ️ Synchronizing existing admin authority: {email}")
        user.set_password(password)  # Utilizing native model cryptographic helper
        user.is_admin = True
        user.is_super_admin = True
        user.role = "super_admin"
        user.is_approved = True
    else:
        click.echo(f"🌱 Creating pristine administrative profile: {email}")
        user = User(
            username=username,
            email=email,
            is_admin=True,
            is_super_admin=True,
            role="super_admin",
            is_approved=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Lock in user.id for downstream foreign keys

    # -------------------------------------------------------------------------
    # 2. Idempotent Downstream Ecosystem Hydration
    # -------------------------------------------------------------------------
    
    if not UserDashboard.query.filter_by(user_id=user.id).first():
        db.session.add(UserDashboard(user_id=user.id))

    if not SubscriberProfile.query.filter_by(user_id=user.id).first():
        profile = SubscriberProfile(user_id=user.id)
        if hasattr(profile, "generate_api_key"):
            profile.generate_api_key()
        db.session.add(profile)

    if not BankInstitution.query.filter_by(institution_id="admin-bank-001").first():
        db.session.add(
            BankInstitution(
                user_id=user.id, 
                name="System Admin Reserve", 
                institution_id="admin-bank-001"
            )
        )

    if not BankAccount.query.filter_by(account_number="9999999999").first():
        db.session.add(
            BankAccount(
                user_id=user.id, 
                account_type="checking", 
                account_number="9999999999", 
                balance=0.0
            )
        )

    # 3. Transaction Lock & Commit
    try:
        db.session.commit()
        click.echo(f"✅ Successfully seeded and verified admin context: {email}")
    except IntegrityError:
        db.session.rollback()
        click.echo("⚠️ ERROR: Integrity conflict detected during admin seed (concurrent process collision?).")
        sys.exit(1)