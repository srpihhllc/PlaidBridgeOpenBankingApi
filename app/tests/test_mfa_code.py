# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_mfa_code.py

# app/tests/test_mfa_code.py

from datetime import datetime, timedelta

from app.models.mfa_code import MFACode


def test_time_remaining_future():
    # Code expires 60 seconds from now
    expires_at = datetime.utcnow() + timedelta(seconds=60)
    mfa_code = MFACode(user_id=1, code="123456", expires_at=expires_at)

    ttl = mfa_code.time_remaining()
    assert ttl > 0
    assert ttl <= 60  # should be within the expected window


def test_time_remaining_expired():
    # Code expired 30 seconds ago
    expires_at = datetime.utcnow() - timedelta(seconds=30)
    mfa_code = MFACode(user_id=1, code="123456", expires_at=expires_at)

    ttl = mfa_code.time_remaining()
    assert ttl == 0  # expired codes return 0


def test_time_remaining_no_expiry():
    # Defensive case: expires_at not set -> treat as expired, return 0
    mfa_code = MFACode(user_id=1, code="123456", expires_at=None)

    ttl = mfa_code.time_remaining()
    assert ttl == 0
