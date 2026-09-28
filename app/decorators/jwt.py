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
