# =============================================================================
# FILE: app/tests/test_totp_flow.py
# DESCRIPTION: CI/CD test for TOTP-based MFA flow.
#              Validates secret generation, code verification, and failure handling.
# =============================================================================

import pyotp

from app.extensions import db
from app.models.user import User
from app.services.totp_service import generate_totp_secret, verify_totp_code


def test_totp_flow(app):
    """
    Validates TOTP MFA flow:
    - Generates a user and TOTP secret
    - Confirms valid code passes
    - Confirms invalid code fails
    """
    with app.app_context():
        # Create test user with TOTP secret
        user = User(username="totp_test", email="totp_test@example.com")
        user.set_password("secret")
        user.totp_secret = generate_totp_secret()
        db.session.add(user)
        db.session.commit()

        # Generate valid TOTP code using pyotp
        valid_code = pyotp.TOTP(user.totp_secret).now()
        assert verify_totp_code(user.totp_secret, valid_code) is True

        # Submit invalid code
        assert verify_totp_code(user.totp_secret, "123456") is False
