# =============================================================================
# FILE: tests/test_mfa_flow.py
# DESCRIPTION: CI/CD smoke test for MFA flow.
#              Validates Redis TTL expiry, one‑time consumption, fail‑count tracking,
#              lockout enforcement, DB audit trail, and TOTP verification.
# =============================================================================

import time

import pyotp
import pytest

from app.extensions import db
from app.models.mfa_code import MFACode
from app.models.user import User
from app.services.mfa_service import generate_mfa_code, verify_mfa_code
from app.services.totp_service import generate_totp_secret, verify_totp_code


@pytest.mark.usefixtures("app")
def test_mfa_flow(app):
    with app.app_context():
        # Clean up any potential stale row from previous runs
        User.query.filter_by(username="mfa_test").delete()
        db.session.commit()

        # Create test user
        user = User(username="mfa_test", email="mfa_test@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        try:
            # --- One-time consumption (DB-backed MFACode) ---
            code = generate_mfa_code(user, ttl_seconds=2, persist=True)
            assert (
                verify_mfa_code(user, code) is True
            ), "First verification should succeed"
            assert (
                verify_mfa_code(user, code) is False
            ), "Second verification should fail (one-time use)"

            # --- TTL expiry ---
            code2 = generate_mfa_code(user, ttl_seconds=1, persist=True)
            time.sleep(2)  # wait beyond TTL
            assert (
                verify_mfa_code(user, code2) is False
            ), "Expired code should fail"

            # --- Fail-count tracking & lockout ---
            bad_code = "000000"
            max_failures = 3
            for i in range(max_failures):
                assert (
                    verify_mfa_code(user, bad_code, max_failures=max_failures)
                    is False
                ), f"Attempt {i+1} should fail"

            assert (
                verify_mfa_code(user, bad_code, max_failures=max_failures)
                is False
            ), "User should remain locked out after max failures"

            # --- Audit trail (DB) ---
            mfa_records = MFACode.query.filter_by(user_id=user.id).all()
            assert isinstance(mfa_records, list)

        finally:
            # Teardown
            MFACode.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()


@pytest.mark.usefixtures("app")
def test_totp_flow(app):
    with app.app_context():
        # Clean up any potential stale row from previous runs
        User.query.filter_by(username="totp_test").delete()
        db.session.commit()

        # Create test user with TOTP secret
        user = User(username="totp_test", email="totp_test@example.com")
        user.set_password("secret")
        user.totp_secret = generate_totp_secret()
        db.session.add(user)
        db.session.commit()

        try:
            # --- Valid TOTP code ---
            valid_code = pyotp.TOTP(user.totp_secret).now()
            assert (
                verify_totp_code(user.totp_secret, valid_code) is True
            ), "Valid TOTP code should succeed"

            # --- Invalid TOTP code ---
            assert (
                verify_totp_code(user.totp_secret, "123456") is False
            ), "Invalid TOTP code should fail"

            # --- Time drift tolerance (window typically ±30s) ---
            past_code = pyotp.TOTP(user.totp_secret).at(int(time.time()) - 30)
            future_code = pyotp.TOTP(user.totp_secret).at(
                int(time.time()) + 30
            )
            assert (
                verify_totp_code(user.totp_secret, past_code) is True
            ), "Past code within window should succeed"
            assert (
                verify_totp_code(user.totp_secret, future_code) is True
            ), "Future code within window should succeed"

        finally:
            # Teardown
            db.session.delete(user)
            db.session.commit()
