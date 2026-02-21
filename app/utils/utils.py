# =============================================================================
# FILE: app/utils/utils.py
# DESCRIPTION: Cockpit-grade authorization helpers and decorators for Flask.
# =============================================================================

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any

from flask import current_app, flash, redirect, request, url_for
from flask_jwt_extended import verify_jwt_in_request
from flask_login import current_user

# =============================================================================
# 🔐 Authorization Helpers
# =============================================================================


def is_admin() -> bool:
    """
    Checks if the current authenticated user is an admin.
    Uses Flask-Login authentication and the `is_admin` attribute.
    """
    return bool(current_user.is_authenticated and getattr(current_user, "is_admin", False))


# =============================================================================
# 🔐 Authorization Decorators
# =============================================================================


def admin_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to restrict access to admin users only.
    Redirects to main.home with a flash message if unauthorized.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not is_admin():
            flash("🚫 You do not have permission to view this page.", "danger")
            current_app.logger.warning(
                "Admin access denied",
                extra={"user_id": getattr(current_user, "id", None)},
            )
            return redirect(url_for("main.home"))
        return f(*args, **kwargs)

    return decorated_function


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator for API endpoints that require authentication.
    Supports both Flask-Login sessions and JWT-based API tokens.
    Returns JSON error responses for API clients when JWT is invalid/missing.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated:
            # Fallback to JWT check for API routes
            if not request.headers.get("Authorization"):
                current_app.logger.warning("Missing Authorization Header on protected route")
                return {
                    "status": "error",
                    "error": {
                        "code": "E_AUTH_FAIL",
                        "message": "Missing Authorization Header",
                    },
                }, 401

            try:
                verify_jwt_in_request()
            except Exception as exc:
                current_app.logger.warning("Invalid or expired JWT", extra={"error": str(exc)})
                return {
                    "status": "error",
                    "error": {
                        "code": "E_AUTH_FAIL",
                        "message": "Invalid or expired token",
                    },
                }, 401

        return f(*args, **kwargs)

    return decorated_function


def roles_required(
    roles: Iterable[str],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to restrict access based on user roles.
    Takes a list or tuple of allowed roles.
    Redirects to main.home with a flash message if unauthorized.
    """

    allowed_roles = set(roles)  # normalize for fast lookup + type clarity

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def decorated_view(*args: Any, **kwargs: Any):
            user_role: str | None = getattr(current_user, "role", None)

            # mypy-safe comparison: user_role is now Optional[str]
            if not current_user.is_authenticated or user_role not in allowed_roles:
                flash(
                    "🚫 You do not have the required role to view this page.",
                    "danger",
                )
                current_app.logger.warning(
                    "Role-based access denied",
                    extra={
                        "user_id": getattr(current_user, "id", None),
                        "role": user_role,
                    },
                )
                return redirect(url_for("main.home"))

            return fn(*args, **kwargs)

        return decorated_view

    return wrapper
