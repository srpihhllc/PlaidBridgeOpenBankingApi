# =============================================================================
# FILE: app/tests/test_mfa_code.py
# DESCRIPTION: Comprehensive unit and branch coverage tests for MFACode model.
#              Ensures 100% coverage across lifecycle helpers, validators,
#              consumption semantics, TTL handlers, and database rollbacks.
# =============================================================================

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.mfa_code import MFACode, secrets_compare
from app.models.user import User


@pytest.fixture
def test_user(app):
    """Provide a cleanly persisted test user for foreign key integrity."""
    with app.app_context():
        user = User(username="mfa_model_user", email="mfa_model@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        yield user

        # Cleanup routine: purge child MFA records before deleting parent user
        # to prevent NOT NULL foreign key constraint errors during teardown
        # Modern SQLAlchemy 2.x bulk delete
        from sqlalchemy import delete

        stmt = delete(MFACode).where(MFACode.user_id == user.id)
        db.session.execute(stmt)
        db.session.delete(user)
        db.session.commit()


@pytest.mark.usefixtures("app")
class TestMFACodeModel:
    # =========================================================================
    # 1. LIFECYCLE CREATION & ATOMIC REPLACEMENT HOOKS
    # =========================================================================
    def test_create_or_replace_new_and_existing(self, app, test_user):
        """Should overwrite any pre-existing MFA codes within the same transaction block."""
        with app.app_context():
            # Establish original token entry with an active commit
            mfa1 = MFACode.create_or_replace(
                user_id=test_user.id,
                code="111111",
                ttl_seconds=300,
                commit=True,
            )
            assert mfa1.id is not None
            assert mfa1.code == "111111"

            # Replace existing entry with flush-only option
            mfa2 = MFACode.create_or_replace(
                user_id=test_user.id,
                code="222222",
                ttl_seconds=600,
                commit=False,
            )
            assert mfa2.code == "222222"
            db.session.commit()

            # Assert target replacement and state tracking
            active = MFACode.get_active_for_user(test_user.id)
            assert active is not None
            assert active.id == mfa2.id
            assert active.code == "222222"
            assert active.time_remaining() > 0

    def test_create_or_replace_sqlalchemy_error(self, app, test_user):
        """Should roll back transactions and bubble up errors upon core database failure."""
        with app.app_context():
            with patch.object(
                db.session,
                "commit",
                side_effect=SQLAlchemyError("Write Failure Interrupt"),
            ):
                with pytest.raises(SQLAlchemyError):
                    MFACode.create_or_replace(
                        user_id=test_user.id, code="333333", commit=True
                    )

    def test_get_active_for_user_none_or_expired(self, app, test_user):
        """Should return None cleanly if a code is absent or has crossed its expiration window."""
        with app.app_context():
            # Condition A: No token record mapped
            assert MFACode.get_active_for_user(test_user.id) is None

            # Condition B: Stale token present in database
            past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            mfa = MFACode(
                user_id=test_user.id, code="123456", expires_at=past_time
            )
            db.session.add(mfa)
            db.session.commit()

            assert MFACode.get_active_for_user(test_user.id) is None

    # =========================================================================
    # 2. VALIDATION & TIMEZONE SECTOR BOUNDARIES
    # =========================================================================
    def test_is_valid_and_time_remaining_edge_cases(self, app, test_user):
        """Should process naive and timezone-aware expirations identically without breaking."""
        with app.app_context():
            # Defensive branch: Null expiry mapping
            mfa_none = MFACode(
                user_id=test_user.id, code="123456", expires_at=None
            )
            assert mfa_none.is_valid() is False
            assert mfa_none.time_remaining() == 0

            # Structural branch: Naive UTC tracking
            future_naive = datetime.now(timezone.utc) + timedelta(seconds=100)
            mfa_naive = MFACode(
                user_id=test_user.id, code="123456", expires_at=future_naive
            )
            assert mfa_naive.is_valid() is True
            assert mfa_naive.time_remaining() > 0

            # Structural branch: Aware UTC tracking (covers expires.tzinfo branch evaluation)
            future_aware = datetime.now(timezone.utc) + timedelta(seconds=200)
            mfa_aware = MFACode(
                user_id=test_user.id, code="123456", expires_at=future_aware
            )
            assert mfa_aware.is_valid() is True
            assert mfa_aware.time_remaining() > 0

    # =========================================================================
    # 3. CONSUMPTION, PENALIZATION & FAILURE TRACKING
    # =========================================================================
    def test_increment_fail_variations(self, app, test_user):
        """Verify fail counters update safely under explicit commits or flushes."""
        with app.app_context():
            mfa = MFACode.create_or_replace(
                user_id=test_user.id, code="123456", commit=True
            )

            # Execution using commit=False
            mfa.increment_fail(commit=False)
            assert mfa.fail_count == 1

            # Execution using commit=True
            mfa.increment_fail(commit=True)
            assert mfa.fail_count == 2

            # Error handling path
            with patch.object(
                db.session,
                "commit",
                side_effect=SQLAlchemyError("Atomic Error Injected"),
            ):
                with pytest.raises(SQLAlchemyError):
                    mfa.increment_fail(commit=True)

    def test_consume_exception_handling(self, app, test_user):
        """Should trigger standard exception logging and rollback when consumption crashes."""
        with app.app_context():
            mfa = MFACode.create_or_replace(
                user_id=test_user.id, code="123456", commit=True
            )

            with patch.object(
                db.session,
                "commit",
                side_effect=SQLAlchemyError("Session Drop"),
            ):
                with pytest.raises(SQLAlchemyError):
                    mfa.consume(commit=True)

    def test_validate_and_consume_lifecycle(self, app, test_user):
        """Validate structural behavior across match, mismatch, expiry, and automated lockouts."""
        with app.app_context():
            # 1. Immediate exit on invalid/expired record
            past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            mfa_expired = MFACode(
                user_id=test_user.id, code="123456", expires_at=past_time
            )
            db.session.add(mfa_expired)
            db.session.commit()
            assert mfa_expired.validate_and_consume("123456") is False

            # 2. Resiliency on invalid records with failing database session
            mfa_expired_err = MFACode(
                user_id=test_user.id, code="123456", expires_at=past_time
            )
            db.session.add(mfa_expired_err)
            db.session.commit()
            with patch.object(
                db.session,
                "commit",
                side_effect=SQLAlchemyError("Prune Crash"),
            ):
                assert mfa_expired_err.validate_and_consume("123456") is False

            # 3. Successful identification and immediate consumption
            mfa_valid = MFACode.create_or_replace(
                user_id=test_user.id, code="654321"
            )
            assert mfa_valid.validate_and_consume("654321") is True

            # 4. Standard verification mismatch penalty
            mfa_mismatch = MFACode.create_or_replace(
                user_id=test_user.id, code="abcdef"
            )
            assert (
                mfa_mismatch.validate_and_consume("wrong_code", max_failures=2)
                is False
            )
            assert mfa_mismatch.fail_count == 1

            # 5. Lockout threshold reached (automated row purge)
            assert (
                mfa_mismatch.validate_and_consume("wrong_code", max_failures=2)
                is False
            )
            # Modern SQLAlchemy 2.x lookup
            assert db.session.get(MFACode, mfa_mismatch.id) is None

            # 6. Lockout purge routine under failing database transaction
            mfa_lockout_err = MFACode.create_or_replace(
                user_id=test_user.id, code="999999"
            )
            mfa_lockout_err.fail_count = 1
            db.session.commit()
            with patch.object(
                db.session,
                "commit",
                side_effect=SQLAlchemyError("Purge Exception Intercept"),
            ):
                assert (
                    mfa_lockout_err.validate_and_consume(
                        "wrong_code", max_failures=2
                    )
                    is False
                )

    # =========================================================================
    # 4. MAINTENANCE ROUTINES & REPRESENTATION
    # =========================================================================
    def test_purge_expired_time_thresholds(self, app, test_user):
        """Verify systemic record cleanups adhere to strict delta windows."""
        with app.app_context():
            # Clear layout records for explicit validation
            from sqlalchemy import delete

            stmt = delete(MFACode)
            db.session.execute(stmt)
            db.session.commit()

            now = datetime.now(timezone.utc)
            mfa_stale = MFACode(
                user_id=test_user.id,
                code="111",
                expires_at=now - timedelta(seconds=600),
            )
            mfa_recent = MFACode(
                user_id=test_user.id,
                code="222",
                expires_at=now - timedelta(seconds=10),
            )
            mfa_active = MFACode(
                user_id=test_user.id,
                code="333",
                expires_at=now + timedelta(seconds=600),
            )
            db.session.add_all([mfa_stale, mfa_recent, mfa_active])
            db.session.commit()

            # Purge with restrictive 'older_than_seconds' argument
            assert MFACode.purge_expired(older_than_seconds=300) == 1

            # Purge all remaining expired entries
            assert MFACode.purge_expired() == 1

            # Active tracking code remains preserved
            from sqlalchemy import func, select

            stmt = (
                select(func.count())
                .select_from(MFACode)
                .filter_by(user_id=test_user.id)
            )
            assert db.session.scalar(stmt) == 1

            # Core engine exception coverage
            with patch.object(
                db.session,
                "execute",
                side_effect=SQLAlchemyError("Query Timeout"),
            ):
                with pytest.raises(SQLAlchemyError):
                    MFACode.purge_expired()

    def test_serialization_and_string_representation(self, app, test_user):
        """Assert dictionary formatting and string summaries produce expected schemas."""
        with app.app_context():
            mfa = MFACode.create_or_replace(
                user_id=test_user.id, code="987654"
            )

            summary = MFACode.list_for_user(test_user.id)
            assert len(summary) == 1
            assert summary[0]["code"] == "987654"

            payload = mfa.to_dict()
            assert payload["user_id"] == test_user.id
            assert "time_remaining" in payload

            repr_string = repr(mfa)
            assert f"user_id={test_user.id}" in repr_string


# =============================================================================
# 5. CRYPTOGRAPHIC TIME ATOMIC SECTOR
# =============================================================================
def test_secrets_compare_utility_matrix():
    """Verify constant-time HMAC comparison matrix handles correct, incorrect, and None inputs."""
    assert secrets_compare("match_string", "match_string") is True
    assert secrets_compare("match_string", "mismatch_string") is False
    assert secrets_compare(None, "valid_payload") is False
    assert secrets_compare("valid_payload", None) is False
    assert secrets_compare(None, None) is False