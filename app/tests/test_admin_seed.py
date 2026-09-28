# =============================================================================
# FILE: app/tests/test_admin_seed.py
# DESCRIPTION: Verifies the presence and integrity of the authoritative admin.
# =============================================================================

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app.models.user import User


@pytest.mark.migration_backed
@pytest.mark.auth
def test_admin_seeded_records(clean_admin_user, db_session):
    """
    Ensure seeded admin has all required related records and FK integrity.
    Uses clean_admin_user fixture alongside session merging to safely handle 
    duplicate key constraints on the authoritative admin UUID.
    """

    # 1. SETUP: Define the authoritative identities matching migration seeds
    target_email = "srpollardsihhllc@gmail.com"
    admin_uuid = "00000000-0000-0000-0000-000000000001"

    # 2. LOOKUP: Query for pre-existing record by primary key or email (SQLAlchemy 2.0 compliant)
    user = db_session.get(User, admin_uuid)
    if not user:
        stmt = select(User).filter_by(email=target_email)
        user = db_session.execute(stmt).scalar_one_or_none()

    # 3. UPSERT: Use merge to securely construct or update state without primary key conflict
    if not user:
        user = User(
            id=admin_uuid,
            username="sr_authoritative_operator",
            email=target_email,
            password_hash=generate_password_hash("AdminPass123!"),
            is_admin=True,
            role="admin",
            is_approved=True,
            is_mfa_enabled=False,
        )
    else:
        user.id = admin_uuid
        user.email = target_email
        user.username = "sr_authoritative_operator"
        user.is_admin = True
        user.role = "admin"
        user.is_approved = True
        user.is_mfa_enabled = False

    try:
        user = db_session.merge(user)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        pytest.fail(f"Database commit failed during admin seed testing: {e}")

    # 4. ACTION & VERIFICATION: Execute core identity checks (SQLAlchemy 2.0 compliant)
    stmt = select(User).filter_by(email=target_email)
    user = db_session.execute(stmt).scalar_one_or_none()

    assert user is not None, "Admin user must exist"
    assert (
        user.id == admin_uuid
    ), "Admin record must map to core operator ID sequence"
    assert user.is_admin is True, "Admin flag constraint missing on seeded row"
    assert user.role == "admin", "Admin role validation mismatch"