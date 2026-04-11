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


def _get_redis_client():
    """
    Resolve a Redis client at call time.

    Preference order:
    1. current_app.redis_client (set during app init)
    2. module-level redis_client imported from app.extensions

    Returns None when no Redis client is available.
    """
    return getattr(current_app, "redis_client", None) or redis_client


def _to_int(value, default=0):
    """Safely convert Redis-returned values (bytes/str/None) to int."""
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        try:
            # bytes -> str
            return int(value.decode() if hasattr(value, "decode") else str(value))
        except Exception:
            return default


def generate_mfa_code(user, ttl_seconds=300, persist=True):
    """
    Generate a one‑time MFA code for a user.
    - Stores ephemeral code in Redis with TTL when available.
    - Optionally persists to DB for audit trail.
    """
    code = str(random.randint(100000, 999999))
    key = f"mfa:{user.id}:{code}"

    client = _get_redis_client()

    # Store in Redis with TTL when available; otherwise continue gracefully.
    if client:
        try:
            # Accept both redis-py client and minimal mocks that support setex
            client.setex(key, timedelta(seconds=ttl_seconds), "valid")
        except Exception as e:
            current_app.logger.warning(
                "⚠️ Failed to set MFA key in Redis (continuing without Redis): %s", e
            )
    else:
        current_app.logger.debug("No Redis client available; skipping Redis storage for MFA.")

    # Persist to DB for audit trail if requested
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
    - Checks Redis for validity when available.
    - Enforces one‑time use by deleting key if present in Redis.
    - Tracks fail‑count in Redis and/or DB.
    - Locks out after max_failures.
    """
    key = f"mfa:{user.id}:{submitted_code}"
    fail_key = f"mfa:fail:{user.id}"

    client = _get_redis_client()

    # Attempt to read fail counter from Redis if available
    if client:
        try:
            raw_fails = client.get(fail_key)
            fails = _to_int(raw_fails, default=0)
        except Exception as e:
            current_app.logger.warning(
                "Redis get for fail counter failed (falling back to DB): %s", e
            )
            client = None  # fall through to DB-only fallback
            fails = 0
    else:
        fails = 0

    if fails >= max_failures:
        current_app.logger.warning(
            f"🚫 User {user.email} locked out after {fails} failed MFA attempts"
        )
        return False

    # Redis-backed path
    if client:
        try:
            val = client.get(key)
            if val == b"valid" or val == "valid":
                try:
                    client.delete(key)  # enforce one‑time use
                    client.delete(fail_key)  # reset fail counter
                except Exception:
                    current_app.logger.debug("Partial Redis cleanup failed after verify.")
                current_app.logger.info(
                    f"✅ MFA code {submitted_code} verified for user {user.email}"
                )
                return True

            # Increment fail counter in Redis
            try:
                client.incr(fail_key)
                client.expire(fail_key, 300)  # expire fail counter after 5 minutes
            except Exception:
                current_app.logger.debug("Failed to increment/expire Redis fail counter.")

            # Update DB fail_count if persisted
            mfa = user.mfa_codes.filter_by(code=submitted_code).first()
            if mfa:
                mfa.fail_count = (mfa.fail_count or 0) + 1
                db.session.add(mfa)
                db.session.commit()

            current_app.logger.warning(
                f"❌ Invalid MFA code {submitted_code} for user {user.email}"
            )
            return False

        except Exception as e:
            current_app.logger.warning(
                "Redis-backed verification failed (falling back to DB-only): %s", e
            )
            # fall through to DB-only fallback

    # DB-only fallback path (no Redis available or Redis errored)
    mfa = user.mfa_codes.filter_by(code=submitted_code).first()
    if mfa and mfa.is_valid():
        try:
            db.session.delete(mfa)
            db.session.commit()
            current_app.logger.info(
                f"✅ MFA code {submitted_code} verified for user {user.email} (DB-only)"
            )
            return True
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to consume MFACode id=%s", getattr(mfa, "id", None))
            return False

    # If not valid or not found, increment DB fail_count if there is a persisted row
    if mfa:
        try:
            mfa.fail_count = (mfa.fail_count or 0) + 1
            db.session.add(mfa)
            if (mfa.fail_count or 0) >= max_failures:
                db.session.delete(mfa)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to update fail_count for MFACode id=%s", getattr(mfa, "id", None))

    current_app.logger.warning(
        f"❌ Invalid MFA code {submitted_code} for user {user.email} (DB-only)"
    )
    return False