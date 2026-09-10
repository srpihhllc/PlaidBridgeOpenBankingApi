# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/decorators/access.py

# app/decorators/access.py
from functools import wraps
from flask import current_app, jsonify, redirect, url_for
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from flask_login import current_user
from werkzeug.exceptions import Forbidden


def user_is_admin():
    """Helper to check if current session user is an admin."""
    if hasattr(current_user, "is_admin"):
        return current_user.is_admin
    if hasattr(current_user, "role"):
        return current_user.role in ("admin", "super_admin")
    return False


def roles_required(*required_roles):
    """
    Decorator that requires the user to have one of the specified roles.
    Supports both JWT tokens (checking claims) and Flask-Login session fallback.

    Behavior:
    - If a valid JWT is present and contains a matching role -> allow.
    - If a valid JWT is present but does NOT contain a matching role -> allow session fallback.
    - If no JWT header is present (Missing/No Authorization) -> fallback to session.
    - If JWT verification raises a structural error (expired, wrong token type, invalid token),
      re-raise it so it bubbles up.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            jwt_verified = False
            jwt_claims = {}
            jwt_attempted = False
            jwt_matched = False

            # 1. Attempt JWT verification
            try:
                verify_jwt_in_request()
                jwt_verified = True
                jwt_claims = get_jwt() or {}
                jwt_attempted = True
            except JWTExtendedException as e:
                # If no token/header was provided, allow fallback to session.
                # If a structural JWT error occurred (expired, bad token type), re-raise immediately.
                if type(e).__name__ in (
                    "NoAuthorizationError",
                    "MissingAuthorizationError",
                ):
                    jwt_verified = False
                else:
                    raise
            except Exception:
                # Any other unexpected exception: treat as no JWT
                jwt_verified = False

            # 2. Evaluate JWT claims if verification succeeded
            if jwt_verified:
                user_roles = jwt_claims.get("roles", [])
                if isinstance(user_roles, str):
                    user_roles = [user_roles]
                single_role = jwt_claims.get("role")
                if single_role and single_role not in user_roles:
                    user_roles.append(single_role)

                if any(r in user_roles for r in required_roles):
                    jwt_matched = True
                    return fn(*args, **kwargs)
                else:
                    jwt_matched = False

            # 3. Fallback to Flask-Login session if no valid JWT header was present or JWT didn't match
            if current_user and getattr(
                current_user, "is_authenticated", False
            ):
                session_roles = []
                if hasattr(current_user, "roles") and current_user.roles:
                    session_roles.extend(current_user.roles)
                if hasattr(current_user, "role") and current_user.role:
                    session_roles.append(current_user.role)
                if getattr(current_user, "is_admin", False):
                    session_roles.append("admin")

                if any(r in session_roles for r in required_roles):
                    return fn(*args, **kwargs)
                else:
                    return jsonify(
                        {"msg": "Forbidden: Insufficient privileges"}
                    ), 403

            # 4. Neither JWT nor session satisfied the required roles
            if jwt_attempted and not jwt_matched:
                return jsonify(
                    {"msg": "Forbidden: Insufficient privileges"}
                ), 403

            # Neither JWT nor session present -> Missing Authorization
            return jsonify({"msg": "Missing Authorization Header"}), 401

        return wrapper

    return decorator


def subscriber_required(fn):
    """Shortcut decorator for subscriber-only endpoints."""
    return roles_required("subscriber")(fn)


def admin_required(fn):
    """Shortcut decorator for admin-only endpoints."""
    return roles_required("admin")(fn)


def super_admin_required(fn):
    """Shortcut decorator for super_admin-only endpoints."""
    return roles_required("super_admin")(fn)


def require_admin(fn):
    """
    Legacy session-only decorator for HTML UI routes.
    Redirects to login if not authenticated, or aborts with 403 if not admin.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
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
