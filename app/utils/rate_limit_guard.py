# =============================================================================
# FILE: app/utils/rate_limit_guard.py
# DESCRIPTION: Safe rate limit decorator for use across all blueprints
# =============================================================================

from functools import wraps

from flask import current_app, has_app_context


def rate_limit_if_enabled(limit_str: str):
    """
    Safe rate limit decorator that respects TESTING and RATE_LIMIT_ENABLED config.

    Returns a pass-through decorator in test mode or when limits are disabled.
    Applies flask_current_app.limiter.Limiter.limit() when rate limiting is enabled.

    This decorator checks config at REQUEST TIME to ensure the app context
    is available and the latest config is used.

    Usage:
        from app.utils.rate_limit_guard import rate_limit_if_enabled

        @app.route("/api/protected")
        @rate_limit_if_enabled("20/hour")
        def protected_endpoint():
            return "success"

    Args:
        limit_str (str): Rate limit string (e.g., "20/hour", "100 per day")

    Returns:
        function: A decorator that conditionally applies rate limiting
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # ⭐ CRITICAL: Check config at REQUEST TIME when app context exists
            if not has_app_context():
                # No app context - just call the function (shouldn't happen in Flask)
                return func(*args, **kwargs)

            is_testing = current_app.config.get("TESTING", False)
            is_rate_limit_enabled = current_app.config.get("RATE_LIMIT_ENABLED", True)

            if is_testing or not is_rate_limit_enabled:
                # Testing mode or rate limiting disabled - skip rate limiting
                return func(*args, **kwargs)

            # Rate limiting enabled - apply the limiter
            rate_limited_func = current_app.limiter.limit(limit_str)(func)
            return rate_limited_func(*args, **kwargs)

        return wrapper

    return decorator


def get_limiter():
    """
    Safely retrieve the current limiter instance.

    Returns:
        Limiter | None: The configured limiter or None if unavailable

    Usage:
        from app.utils.rate_limit_guard import get_limiter

        limiter = get_limiter()
        # Use limiter.limit() or other limiter methods
    """
    if not has_app_context():
        return None
    return getattr(current_app, "limiter", None)
