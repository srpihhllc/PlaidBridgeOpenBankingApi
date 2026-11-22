# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/decorators/jwt.py
"""
JWT Access Control Decorators for PlaidBridgeOpenBankingApi[cite: 1].
Delegates authorization and tier checks to unified access handlers backed by PolicyEngine[cite: 1].
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException

from app.decorators.access import roles_required as unified_roles_required


def roles_required(*required_roles):
    """
    Unified JWT Roles check[cite: 1].
    Ensures a valid JWT is present and evaluates required roles/tiers via PolicyEngine[cite: 1].
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except JWTExtendedException as e:
                return jsonify({
                    "msg": "Missing, expired, or invalid JWT token",
                    "error": str(e)
                }), 401
            except Exception as e:
                return jsonify({
                    "msg": "JWT authentication failed",
                    "error": str(e)
                }), 401

            return unified_roles_required(*required_roles)(fn)(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn):
    """Unified JWT Admin check[cite: 1]. Delegates to PolicyEngine via unified_roles_required[cite: 1]."""
    return roles_required("admin")(fn)


def subscriber_required(fn):
    """Unified JWT Subscriber check[cite: 1]. Delegates to PolicyEngine via unified_roles_required[cite: 1]."""
    return roles_required("subscriber")(fn)


def super_admin_required(fn):
    """Unified JWT Super Admin check[cite: 1]. Delegates to PolicyEngine via unified_roles_required[cite: 1]."""
    return roles_required("super_admin")(fn)





def session_or_jwt_required(fn):

    """Allow either an active Flask-Login session or a valid Bearer JWT."""

    @wraps(fn)

    def wrapper(*args, **kwargs):

        from flask_login import current_user, login_user

        if getattr(current_user, "is_authenticated", False):

            return fn(*args, **kwargs)



        try:

            verify_jwt_in_request()

            from flask_jwt_extended import get_jwt_identity

            from app.models.user import User

            identity = get_jwt_identity()

            user = User.query.get(int(identity)) if identity is not None else None

            if user is not None:

                login_user(user, remember=False)

                return fn(*args, **kwargs)

        except Exception as exc:

            return jsonify({

                "msg": "Authentication required (valid session or Bearer JWT)",

                "error": str(exc),

            }), 401



        return jsonify({"msg": "Authenticated user not found"}), 401



    return wrapper

