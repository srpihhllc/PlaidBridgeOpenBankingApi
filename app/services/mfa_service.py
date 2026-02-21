# =============================================================================
# FILE: app/services/mfa_service.py
# DESCRIPTION: Redis‑backed MFA service with TTL expiry, one‑time use enforcement,
#              fail‑count tracking, and optional DB persistence for audit trails.
# =============================================================================
import random
from datetime import datetime, timedelta

from flask import current_app
from flask_mail import Message

from app.extensions import db, mail, redis_client
from app.models.mfa_code import MFACode


def generate_mfa_code(user, ttl_seconds=300, persist=True):
    """
    Generate a one‑time MFA code for a user.
    - Stores ephemeral code in Redis with TTL.
    - Optionally persists to DB for audit trail.
    """
    code = str(random.randint(100000, 999999))
    key = f"mfa:{user.id}:{code}"

    # Store in Redis with TTL
    redis_client.setex(key, timedelta(seconds=ttl_seconds), "valid")

    # Persist to DB for audit trail
    if persist:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        mfa = MFACode(user_id=user.id, code=code, expires_at=expires_at)
        db.session.add(mfa)
        db.session.commit()

    current_app.logger.info(
        f"✅ MFA code {code} generated for user {user.email} with TTL={ttl_seconds}s"
    )
    return code


def send_mfa_code(user, ttl_seconds=300, persist=True):
    """
    Generate and deliver MFA code via email.
    """
    code = generate_mfa_code(user, ttl_seconds=ttl_seconds, persist=persist)
    msg = Message(
        subject="Your MFA Code",
        recipients=[user.email],
        body=f"Your MFA verification code is: {code}",
    )
    mail.send(msg)
    current_app.logger.info(f"📩 MFA code {code} sent to {user.email}")
    return code


def verify_mfa_code(user, submitted_code, max_failures=3):
    """
    Verify MFA code:
    - Checks Redis for validity.
    - Enforces one‑time use by deleting key.
    - Tracks fail‑count in Redis and DB.
    - Locks out after max_failures.
    """
    key = f"mfa:{user.id}:{submitted_code}"
    fail_key = f"mfa:fail:{user.id}"

    # Check if user is locked out
    fails = int(redis_client.get(fail_key) or 0)
    if fails >= max_failures:
        current_app.logger.warning(
            f"🚫 User {user.email} locked out after {fails} failed MFA attempts"
        )
        return False

    if redis_client.get(key) == b"valid":
        redis_client.delete(key)  # enforce one‑time use
        redis_client.delete(fail_key)  # reset fail counter
        current_app.logger.info(f"✅ MFA code {submitted_code} verified for user {user.email}")
        return True

    # Increment fail counter
    redis_client.incr(fail_key)
    redis_client.expire(fail_key, 300)  # expire fail counter after 5 minutes

    # Update DB fail_count if persisted
    mfa = user.mfa_codes.filter_by(code=submitted_code).first()
    if mfa:
        mfa.fail_count += 1
        db.session.commit()

    current_app.logger.warning(
        f"❌ Invalid MFA code {submitted_code} for user {user.email} (fail_count={fails+1})"
    )
    return False
