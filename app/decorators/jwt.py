# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/decorators/jwt.py

from functools import wraps

from flask_jwt_extended import verify_jwt_in_request

# Import the unified logic from your access.py
from app.decorators.access import roles_required as unified_roles_required


def admin_required(fn):
    """
    Unified Admin check.
    Uses the hybrid logic from access.py but ensures JWT is present.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Ensure a valid JWT exists before proceeding to role check
        verify_jwt_in_request()
        return unified_roles_required("admin")(fn)(*args, **kwargs)

    return wrapper


def roles_required(*required_roles):
    """
    Unified Roles check.
    Ensures JWT is present and matches the roles required.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            return unified_roles_required(*required_roles)(fn)(*args, **kwargs)

        return wrapper

    return decorator
