# =============================================================================
# FILE: app/services/mfa_service.py
# DESCRIPTION: Unified Redis & DB-backed MFA service with atomic replacement,
#              proper DB fallback, constant-time verification, and lockout handling.
# =============================================================================

import logging
import secrets

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
    except (TypeError, ValueError):
        try:
            decoded = value.decode() if hasattr(value, "decode") else str(value)
            return int(decoded)
        except (TypeError, ValueError, UnicodeDecodeError):
            return default


def generate_mfa_code(user, ttl_seconds=300, persist=True) -> str:
    """Generate a cryptographically secure six-digit MFA code."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than zero")

    code = f"{secrets.randbelow(1_000_000):06d}"
    user_id = str(user.id)
    redis_key = f"mfa:{user_id}:{code}"
    client = _get_redis_client()

    if client:
        try:
            client.setex(redis_key, ttl_seconds, "valid")
        except Exception:
            logger.exception("Failed to store MFA code in Redis for user_id=%s", user_id)

    if persist:
        MFACode.create_or_replace(
            user_id=user_id,
            code=code,
            ttl_seconds=ttl_seconds,
            commit=True,
        )

    # Never log the code itself.
    logger.info("MFA code generated for user_id=%s", user_id)
    return code


def send_mfa_code(user, ttl_seconds=300, persist=True) -> str:
    """Generate and send an MFA code using the configured Flask-Mail backend."""
    email = getattr(user, "email", None)
    if not email:
        raise ValueError("User has no email address configured for MFA")

    code = generate_mfa_code(
        user,
        ttl_seconds=ttl_seconds,
        persist=persist,
    )

    message = Message(
        subject="Your MFA Code",
        recipients=[email],
        body=f"Your MFA verification code is: {code}",
    )

    try:
        mail.send(message)
    except Exception:
        logger.exception("Failed to send MFA email for user_id=%s", user.id)
        raise

    logger.info("MFA email sent for user_id=%s", user.id)
    return code


def verify_mfa_code(user, submitted_code: str, max_failures: int = 3) -> bool:
    """Verify and consume an active MFA code using Redis with a DB fallback."""
    if submitted_code is None:
        return False

    user_id = str(user.id)
    submitted_code = str(submitted_code).strip()
    if not submitted_code:
        return False

    redis_key = f"mfa:{user_id}:{submitted_code}"
    fail_key = f"mfa:fail:{user_id}"
    client = _get_redis_client()

    # Lockout check.
    if client:
        try:
            failures = _to_int(client.get(fail_key), default=0)
            if failures >= max_failures:
                logger.warning("MFA lockout for user_id=%s", user_id)
                return False
        except Exception:
            logger.exception("Could not read MFA failure count for user_id=%s", user_id)
            client = None

    # Redis verification path.
    if client:
        try:
            value = client.get(redis_key)
            if value in (b"valid", "valid"):
                client.delete(redis_key)
                client.delete(fail_key)

                # Consume the matching database record too, if one exists.
                active_record = MFACode.get_active_for_user(user_id)
                if active_record:
                    active_record.consume(commit=True)

                logger.info("MFA code verified via Redis for user_id=%s", user_id)
                return True
        except Exception:
            logger.exception("Redis MFA verification failed for user_id=%s", user_id)

    # Database fallback.
    active_record = MFACode.get_active_for_user(user_id)
    if active_record and active_record.validate_and_consume(
        submitted_code,
        max_failures=max_failures,
    ):
        if client:
            try:
                client.delete(fail_key)
            except Exception:
                logger.exception(
                    "Could not clear MFA failure count for user_id=%s", user_id
                )

        logger.info("MFA code verified via database for user_id=%s", user_id)
        return True

    # Record failed attempt.
    if client:
        try:
            client.incr(fail_key)
            client.expire(fail_key, 300)
        except Exception:
            logger.exception("Could not record MFA failure for user_id=%s", user_id)

    logger.warning("Invalid MFA code attempt for user_id=%s", user_id)
    return False