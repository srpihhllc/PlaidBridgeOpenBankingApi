# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/tests/test_admin_seed.py

import pytest

from app.models import BankAccount, BankInstitution, SubscriberProfile, User, UserDashboard


# Markers: run this with your migration-backed and auth tests
@pytest.mark.migration_backed
@pytest.mark.auth
def test_admin_seeded_records(db_session):
    """Ensure seeded admin has all required related records and FK integrity."""

    user = db_session.query(User).filter_by(email="srpollardsihhllc@gmail.com").first()
    assert user is not None, "Admin user must exist"
    assert user.is_admin, "Admin flag must be set"

    # Dashboard
    dashboard = db_session.query(UserDashboard).filter_by(user_id=user.id).first()
    assert dashboard is not None, "Admin must have a dashboard"
    assert dashboard.user_id == user.id, "Dashboard FK must match admin user_id"

    # Subscriber profile
    profile = db_session.query(SubscriberProfile).filter_by(user_id=user.id).first()
    assert profile is not None, "Admin must have a subscriber profile"
    assert profile.user_id == user.id, "SubscriberProfile FK must match admin user_id"

    # Bank institution
    institution = db_session.query(BankInstitution).filter_by(user_id=user.id).first()
    assert institution is not None, "Admin must have a bank institution"
    assert institution.user_id == user.id, "BankInstitution FK must match admin user_id"

    # Bank account
    account = db_session.query(BankAccount).filter_by(user_id=user.id).first()
    assert account is not None, "Admin must have a bank account"
    assert account.user_id == user.id, "BankAccount FK must match admin user_id"
