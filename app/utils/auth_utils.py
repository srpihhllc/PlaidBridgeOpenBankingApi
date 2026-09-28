# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/auth_utils.py
"""
Authentication & Session Utility Helpers for PlaidBridgeOpenBankingApi[cite: 1].
Delegates all authorization evaluations to PolicyEngine, eliminating fragile
circular imports, raw session flag checks, and scattered privilege logic[cite: 1].
"""

import hmac
import os
from functools import wraps

from flask import abort, current_app, jsonify, request
from flask_login import current_user

from app.security.policy_engine import PolicyEngine, SecurityTier


def admin_required(f):
    """
    Decorator to restrict access to authenticated users or operators
    with Admin tier or higher. Delegates privilege resolution to PolicyEngine[cite: 1].
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not PolicyEngine.evaluate_request(SecurityTier.ADMIN):
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def require_api_key(f):
    """
    Decorator requiring a valid API key in 'X-API-KEY' header[cite: 1].
    Uses constant-time comparison (hmac.compare_digest) to eliminate timing attacks[cite: 1].
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.getenv("API_KEY")
        if not api_key:
            current_app.logger.error("API_KEY environment variable is not set.")
            return jsonify({"error": "Internal server error"}), 500

        provided_key = request.headers.get("X-API-KEY")
        if not provided_key or not hmac.compare_digest(provided_key, api_key):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return decorated_function


def require_subscriber():
    """
    Hard guard returning current_user if caller satisfies SUBSCRIBER tier or higher[cite: 1]
    (including System Operators resolved via PolicyEngine)[cite: 1].
    """
    if not getattr(current_user, "is_authenticated", False):
        if not PolicyEngine.evaluate_request(SecurityTier.SUBSCRIBER):
            abort(401)

    if not PolicyEngine.evaluate_request(SecurityTier.SUBSCRIBER):
        abort(403)

    return current_user
