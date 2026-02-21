# =============================================================================
# FILE: app/services/rate_limiter.py
# DESCRIPTION: Redis-backed rate limiting service for login, MFA, and other
#              sensitive endpoints. Provides cockpit-grade protection against
#              brute force and abuse.
# =============================================================================

import logging

from app.utils.redis_utils import get_redis_client

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Key Construction
# -----------------------------------------------------------------------------
def _make_key(identifier: str, action: str) -> str:
    """
    Construct a Redis key for rate limiting.
    Example: pulse:ratelimit:login:127.0.0.1
    """
    return f"pulse:ratelimit:{action}:{identifier}"


# -----------------------------------------------------------------------------
# Rate Limit Check
# -----------------------------------------------------------------------------
def is_rate_limited(identifier: str, action: str, limit: int, period: int) -> bool:
    """
    Check if the given identifier (IP, user_id, etc.) has exceeded the rate limit.

    Args:
        identifier (str): Unique identifier (IP address, user_id, etc.)
        action (str): Action name (e.g., "login", "mfa_prompt")
        limit (int): Max allowed attempts within the period
        period (int): Time window in seconds

    Returns:
        bool: True if rate limited, False otherwise
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis unavailable — skipping rate limit check (fail-open).")
        return False

    key = _make_key(identifier, action)
    try:
        count = client.get(key)
        if count is None:
            return False
        try:
            return int(count) >= limit
        except ValueError:
            logger.error(f"Non-integer value found in rate limit key {key}: {count}")
            client.delete(key)
            return False
    except Exception as e:
        logger.error(f"Rate limit check failed for {key}: {e}", exc_info=True)
        return False


# -----------------------------------------------------------------------------
# Rate Limit Increment
# -----------------------------------------------------------------------------
def apply_rate_limit(
    identifier: str,
    action: str,
    is_failure: bool = False,
    limit: int = 5,
    period: int = 60,
) -> None:
    """
    Increment the rate limit counter for the given identifier/action.

    Args:
        identifier (str): Unique identifier (IP address, user_id, etc.)
        action (str): Action name
        is_failure (bool): Whether this was a failed attempt (default: False)
        limit (int): Max allowed attempts
        period (int): Time window in seconds
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis unavailable — skipping rate limit increment (fail-open).")
        return

    key = _make_key(identifier, action)
    try:
        # Use pipeline for atomic increment + expiry
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, period)
        pipe.execute()

        if is_failure:
            logger.info(
                f"Rate limit incremented for {key} (failure). " f"Limit={limit}, Period={period}s"
            )
        else:
            logger.info(
                f"Rate limit incremented/reset for {key} (success). "
                f"Limit={limit}, Period={period}s"
            )
    except Exception as e:
        logger.error(f"Failed to apply rate limit for {key}: {e}", exc_info=True)
