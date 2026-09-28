# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/decorators/access.py
"""
Unified access-control decorators for PlaidBridgeOpenBankingApi.

Authorization decisions are delegated to app.security.policy_engine while
supporting JWT authentication, Flask-Login sessions, and legacy UI routes.
"""

from functools import wraps

from flask import (
    abort,
    current_app,
    has_request_context,
    jsonify,
    redirect,
    session,
    url_for,
)
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from flask_login import current_user
from werkzeug.exceptions import Forbidden

from app.security.policy_engine import (
    ROLE_TIER_MAP,
    PolicyEngine,
    SecurityTier,
)


def user_is_admin() -> bool:
    """
    Return whether the current user has administrator privileges.

    Direct user attributes are checked first so this helper can safely be
    used outside a Flask request context, including unit tests and CLI code.
    PolicyEngine is consulted only when a request context is available.
    """
    user_role = getattr(current_user, "role", None)

    if user_role in ("admin", "super_admin"):
        return True

    if getattr(current_user, "is_admin", False) is True:
        return True

    if not has_request_context():
        return False

    return bool(PolicyEngine.evaluate_request(SecurityTier.ADMIN))


def has_permission(user_or_perm, permission=None):
    """
    Check a user's permission or return a permission-checking decorator.

    Function usage:

        has_permission(user, "read_operational_data")

    Decorator usage:

        @has_permission("read_operational_data")
    """

    # Function form:
    # has_permission(user, "permission_name")
    if permission is not None or not isinstance(user_or_perm, str):
        user = user_or_perm
        requested_permission = permission

        if user and getattr(user, "is_authenticated", False):
            user_permissions = (
                getattr(user, "permissions", set()) or set()
            )

            if isinstance(user_permissions, (list, tuple, set)):
                if (
                    requested_permission in user_permissions
                    or "all" in user_permissions
                ):
                    return True

        if not has_request_context():
            return False

        return bool(PolicyEngine.evaluate_request(SecurityTier.ADMIN))

    # Decorator form:
    # @has_permission("permission_name")
    requested_permission = user_or_perm

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            authenticated = bool(
                current_user
                and getattr(current_user, "is_authenticated", False)
            )

            if not authenticated and not user_is_admin():
                abort(401)

            if not has_permission(current_user, requested_permission):
                abort(403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(*required_roles):
    """
    Require the caller to satisfy at least one of the required roles.

    JWT claims and Flask-Login sessions are evaluated uniformly through
    PolicyEngine.
    """
    target_tiers = [
        ROLE_TIER_MAP.get(
            str(role).lower(),
            SecurityTier.GUEST,
        )
        for role in required_roles
    ]

    min_required_tier = (
        min(target_tiers)
        if target_tiers
        else SecurityTier.GUEST
    )

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            jwt_verified = False
            jwt_claims = {}
            jwt_attempted = False

            # Inspect and verify the Authorization header.
            try:
                verify_jwt_in_request()
                jwt_verified = True
                jwt_claims = get_jwt() or {}
                jwt_attempted = True

            except JWTExtendedException as exc:
                exception_name = type(exc).__name__

                if exception_name in {
                    "NoAuthorizationError",
                    "MissingAuthorizationError",
                }:
                    jwt_attempted = False
                else:
                    raise

            except Exception:
                # Preserve fallback behavior for malformed or unsupported JWT
                # processing errors.
                pass

            authenticated = bool(
                getattr(current_user, "is_authenticated", False)
            )

            active_session = session if session else None

            effective_tier = PolicyEngine.resolve_effective_tier(
                user=current_user if authenticated else None,
                session_obj=active_session,
                jwt_claims=jwt_claims if jwt_verified else None,
            )

            if effective_tier >= min_required_tier:
                return fn(*args, **kwargs)

            # A JWT was attempted but could not be verified.
            if jwt_attempted and not jwt_verified:
                return (
                    jsonify(
                        {
                            "msg": (
                                "Missing Authorization Header or "
                                "Invalid Token"
                            )
                        }
                    ),
                    401,
                )

            # An authenticated session or verified JWT lacks sufficient
            # privileges.
            if authenticated or jwt_verified:
                return (
                    jsonify(
                        {
                            "msg": (
                                "Forbidden: Insufficient privileges"
                            )
                        }
                    ),
                    403,
                )

            return (
                jsonify({"msg": "Missing Authorization Header"}),
                401,
            )

        return wrapper

    return decorator


def subscriber_required(fn):
    """Require subscriber-level access."""
    return roles_required("subscriber")(fn)


def admin_required(fn):
    """Require administrator-level access."""
    return roles_required("admin")(fn)


def super_admin_required(fn):
    """Require super-administrator-level access."""
    return roles_required("super_admin")(fn)


def require_admin(fn):
    """
    Protect a legacy session-based HTML route.

    Unauthenticated users are redirected to the login endpoint. Authenticated
    users without administrator privileges receive HTTP 403.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        authenticated = bool(
            current_user
            and getattr(current_user, "is_authenticated", False)
        )

        if not authenticated and not user_is_admin():
            login_endpoint = (
                "auth.login"
                if "auth.login" in current_app.view_functions
                else "login"
            )

            try:
                return redirect(url_for(login_endpoint))
            except Exception:
                return redirect("/mock-login")

        if not user_is_admin():
            raise Forbidden()

        return fn(*args, **kwargs)

    return wrapper
