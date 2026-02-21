# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/decorators/access.py

from functools import wraps

from flask import abort, flash, jsonify, redirect, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
from flask_login import current_user

from app.utils.telemetry import log_identity_event  # ← FIXED IMPORT
from app.utils.user_helpers import user_is_admin


# =============================================================================
# 1. ROLE-BASED ACCESS (JWT-aware + Flask-Login fallback)
# =============================================================================
def roles_required(*required_roles):
    """
    Role-based access decorator that supports BOTH JWT and Flask-Login.
    Ensures compatibility between API tests (JWT) and UI usage (Session).
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # -------------------------------------------------------------
            # 1.1 JWT PATH (Priority for API calls)
            # -------------------------------------------------------------
            try:
                verify_jwt_in_request(optional=True)
                claims = get_jwt()

                if claims:
                    jwt_roles = claims.get("roles", [])
                    is_admin_claim = claims.get("is_admin", False)

                    # Match explicit roles OR allow is_admin=True to satisfy admin routes
                    if any(role in jwt_roles for role in required_roles) or (
                        is_admin_claim and "admin" in required_roles
                    ):
                        return fn(*args, **kwargs)

            except Exception:
                # No valid JWT — fall back to session
                pass

            # -------------------------------------------------------------
            # 1.2 FLASK-LOGIN FALLBACK (UI sessions)
            # -------------------------------------------------------------
            if getattr(current_user, "is_authenticated", False):
                user_role = getattr(current_user, "role", None)
                user_is_admin_attr = getattr(current_user, "is_admin", False)

                if user_role in required_roles or (
                    user_is_admin_attr and "admin" in required_roles
                ):
                    return fn(*args, **kwargs)

            # -------------------------------------------------------------
            # 1.3 ACCESS DENIED
            # -------------------------------------------------------------
            log_identity_event(
                event_type="ROLE_ACCESS_DENIED",
                user_id=get_jwt_identity() or getattr(current_user, "id", 0),
                details={
                    "required_roles": list(required_roles),
                    "reason": "missing_required_role_or_claim",
                },
            )

            return (
                jsonify(
                    {
                        "msg": "Forbidden",
                        "error": "You don't have permission to access this resource.",
                    }
                ),
                403,
            )

        return wrapper

    return decorator


# =============================================================================
# 2. SHORTCUT DECORATORS
# =============================================================================
def admin_required(fn):
    """Shortcut for routes requiring 'admin' privileges."""
    return roles_required("admin")(fn)


def super_admin_required(fn):
    """Shortcut for routes requiring 'super_admin' privileges."""
    return roles_required("super_admin")(fn)


# =============================================================================
# 3. UI-SPECIFIC LEGACY CHECK (Session-only admin gate)
# =============================================================================
def require_admin(view_func):
    """Legacy session-only redirect for UI routes."""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # 3.1 Must be logged in
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "info")
            return redirect(url_for("auth.login"))

        # 3.2 Must be super admin
        if not user_is_admin(current_user):
            abort(403)

        return view_func(*args, **kwargs)

    return wrapped_view
