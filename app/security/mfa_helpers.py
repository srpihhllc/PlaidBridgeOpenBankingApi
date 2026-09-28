# app/security/mfa_helpers.py
import logging
import time
from typing import Optional
from flask import current_app

logger = logging.getLogger(__name__)

# Fallback window & threshold constants (configurable via Flask config)
DEFAULT_MAX_SENDS_PER_WINDOW = 3   # Max MFA requests allowed
DEFAULT_WINDOW_SECONDS = 600       # 10-minute sliding/fixed window


def _get_redis_client():
    """Extract Redis client from application context or state."""
    try:
        # Check Flask app redis client
        client = getattr(current_app, "redis_client", None)
        if client:
            return client
            
        # Check Flask extensions mapping
        extensions = getattr(current_app, "extensions", {})
        if "redis" in extensions:
            return extensions["redis"]
        if "flask_redis" in extensions:
            return extensions["flask_redis"]
            
    except Exception as err:
        logger.warning(f"Unable to resolve Redis client from current_app: {err}")
    
    return None


def _build_rate_limit_key(identifier_type: str, identifier: str) -> str:
    """Build a deterministic Redis key for MFA rate limiting."""
    return f"mfa_rate_limit:{identifier_type}:{identifier}"


def check_mfa_send_rate_limit(
    user_id: Optional[str], ip_address: Optional[str] = None
) -> bool:
    """
    Check whether an MFA send request is allowed under current rate limits.
    Returns True if allowed, False if limit exceeded.
    """
    redis_conn = _get_redis_client()
    if not redis_conn:
        logger.error("Redis client unavailable; failing open for MFA rate limit check.")
        return True

    max_sends = current_app.config.get("MFA_MAX_SENDS_PER_WINDOW", DEFAULT_MAX_SENDS_PER_WINDOW)

    keys_to_check = []
    if user_id:
        keys_to_check.append(_build_rate_limit_key("user", str(user_id)))
    if ip_address:
        keys_to_check.append(_build_rate_limit_key("ip", str(ip_address)))

    if not keys_to_check:
        return True

    try:
        # Retrieve current counters in a single pipeline
        pipe = redis_conn.pipeline()
        for key in keys_to_check:
            pipe.get(key)
        results = pipe.execute()

        for count in results:
            if count is not None and int(count) >= max_sends:
                logger.warning("MFA rate limit exceeded for request.")
                return False

        return True

    except Exception as exc:
        logger.exception(f"Error checking MFA send rate limit in Redis: {exc}")
        return True  # Fail open to prevent blocking legitimate MFA requests during Redis degradations


def record_mfa_send_request(
    user_id: Optional[str],
    ip_address: Optional[str] = None,
    channel: str = "sms",
    masked_dest: Optional[str] = None,
) -> None:
    """
    Increment Redis counters and audit logging for an MFA dispatch attempt.
    """
    redis_conn = _get_redis_client()
    window = current_app.config.get("MFA_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS)

    keys_to_increment = []
    if user_id:
        keys_to_increment.append(_build_rate_limit_key("user", str(user_id)))
    if ip_address:
        keys_to_increment.append(_build_rate_limit_key("ip", str(ip_address)))

    if redis_conn and keys_to_increment:
        try:
            pipe = redis_conn.pipeline()
            for key in keys_to_increment:
                pipe.incr(key)
                pipe.expire(key, window)
            pipe.execute()
        except Exception as exc:
            logger.exception(f"Failed to record MFA send request counter in Redis: {exc}")

    # Audit log entry
    logger.info(
        "MFA send request recorded | Channel: %s | User: %s | IP: %s | Destination: %s",
        channel,
        user_id or "N/A",
        ip_address or "N/A",
        masked_dest or "N/A",
    )