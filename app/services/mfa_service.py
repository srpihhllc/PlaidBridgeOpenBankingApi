# =============================================================================
# FILE: app/services/mfa_service.py
# DESCRIPTION: Unified Redis & DB-backed MFA service with atomic replacement,
#              proper DB fallback, constant-time verification, and lockout handling.
# =============================================================================

import random
import logging
from flask import current_app
from flask_mail import Message

from app.extensions import mail, redis_client
from app.models.mfa_code import MFACode

logger = logging.getLogger(__name__)


def _get_redis_client():
    return getattr(current_app, "redis_client", None) or redis_client


def _to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        try:
            return int(value.decode() if hasattr(value, "decode") else str(value))
        except Exception:
            return default


def generate_mfa_code(user, ttl_seconds=300, persist=True) -> str:
    """
    Generate a 6-digit MFA code, store in Redis, and atomically create/replace 
    the active row in the DB via MFACode.create_or_replace.
    """
    code = f"{random.randint(0, 999999):06d}"
    redis_key = f"mfa:{user.id}:{code}"
    client = _get_redis_client()

    if client:
        try:
            client.setex(redis_key, ttl_seconds, "valid")
        except Exception as e:
            logger.warning("⚠️ Failed to set MFA key in Redis: %s", e)

    if persist:
        # Uses classmethod to clear old codes and avoid timezone mismatches
        MFACode.create_or_replace(
            user_id=str(user.id),
            code=code,
            ttl_seconds=ttl_seconds,
            commit=True,
        )

    logger.info("✅ MFA code %s generated for user %s", code, user.email)
    return code


def send_mfa_code(user, ttl_seconds=300, persist=True) -> str:
    """Generate and send MFA code via email."""
    code = generate_mfa_code(user, ttl_seconds=ttl_seconds, persist=persist)
    msg = Message(
        subject="Your MFA Code",
        recipients=[user.email],
        body=f"Your MFA verification code is: {code}",
    )
    mail.send(msg)
    logger.info("📩 MFA code sent to %s", user.email)
    return code


def verify_mfa_code(user, submitted_code: str, max_failures: int = 3) -> bool:
    """
    Verify MFA code with dual Redis/DB checks, fail-counter tracking, and atomic consumption.
    """
    user_id_str = str(user.id)
    submitted_code = str(submitted_code).strip()
    redis_key = f"mfa:{user_id_str}:{submitted_code}"
    fail_key = f"mfa:fail:{user_id_str}"
    client = _get_redis_client()

    # 1. Lockout Check (Redis)
    if client:
        try:
            fails = _to_int(client.get(fail_key), default=0)
            if fails >= max_failures:
                logger.warning("🚫 User %s locked out via Redis fail-counter", user.email)
                return False
        except Exception as e:
            logger.warning("Redis error reading fail counter: %s", e)
            client = None

    # 2. Redis-backed Verification Path
    if client:
        try:
            val = client.get(redis_key)
            if val in (b"valid", "valid"):
                client.delete(redis_key)
                client.delete(fail_key)
                
                # Sync DB by consuming active code if present
                active_db_mfa = MFACode.get_active_for_user(user_id_str)
                if active_db_mfa:
                    active_db_mfa.consume(commit=True)
                
                logger.info("✅ MFA code %s verified via Redis for %s", submitted_code, user.email)
                return True
        except Exception as e:
            logger.warning("Redis verification failed, dropping to DB fallback: %s", e)

    # 3. DB Fallback Path (Runs if Redis missed, expired early, or threw error)
    active_mfa = MFACode.get_active_for_user(user_id_str)
    if active_mfa:
        is_valid = active_mfa.validate_and_consume(submitted_code, max_failures=max_failures)
        if is_valid:
            if client:
                try:
                    client.delete(fail_key)
                except Exception:
                    pass
            logger.info("✅ MFA code %s verified via DB for %s", submitted_code, user.email)
            return True

    # 4. Handle Invalid Submission
    if client:
        try:
            client.incr(fail_key)
            client.expire(fail_key, 300)
        except Exception:
            pass

    logger.warning("❌ Invalid MFA code attempt for user %s", user.email)
    return False