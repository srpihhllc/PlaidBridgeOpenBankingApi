# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/auth_utils.py

# =====================
# ⚙️ Standard Libraries
# =====================
import os
from functools import wraps

# =====================
# 🧠 Flask + Extensions
# =====================
from flask import abort, current_app, jsonify, request
from flask_login import current_user


def admin_required(f):
    """
    Decorator to restrict access to a view to authenticated
    users with the 'is_admin' attribute set to True.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if the user is authenticated and is an admin
        if not current_user.is_authenticated or not current_user.is_admin:
            # Abort with a 403 Forbidden error
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def require_api_key(f):
    """
    Decorator to require a valid API key for a view.
    The key is expected in the 'X-API-KEY' header.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.getenv("API_KEY")
        if not api_key:
            current_app.logger.error(
                "API_KEY environment variable is not set."
            )
            return jsonify({"error": "Internal server error"}), 500

        provided_key = request.headers.get("X-API-KEY")
        if not provided_key or provided_key != api_key:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return decorated_function


# =============================================================================
# ⚓ SUBSCRIBER & CREATOR BYPASS GUARD
# =============================================================================
def require_subscriber():
    """
    Hard guard: only authenticated subscribers may access these routes.
    Operators/Creators bypass the role check.
    """
    if not getattr(current_user, "is_authenticated", False):
        abort(401)

    # 💡 OPERATOR BYPASS (Local imports prevent circular dependency loops)
    from flask import session

    from app.blueprints.main_routes import is_creator
    from app.constants import OPERATOR_MODE_KEY

    # If session flag is set OR user matches creator profile, open the gates
    if session.get(OPERATOR_MODE_KEY) is True or is_creator(current_user):
        return current_user

    # 🔒 STANDARD SUBSCRIBER CHECK
    if getattr(current_user, "role", None) != "subscriber":
        abort(403)

    return current_user
