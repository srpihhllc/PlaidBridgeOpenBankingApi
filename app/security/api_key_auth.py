# =============================================================================
# FILE: app/security/api_key_auth.py
# DESCRIPTION: API Key authentication for public endpoints
# =============================================================================

import hashlib
import hmac
import os
from collections.abc import Callable
from functools import wraps

from flask import abort, current_app, g, request

# Store API keys in memory (in production, use a database)
# Format: {'client_id': {'api_key': 'hashed_key', 'permissions': ['read', 'write']}}
API_KEYS: dict[str, dict] = {}


def init_api_keys():
    """Initialize API keys from environment or config"""
    # Add a default key for testing (remove in production)
    API_KEYS["default_client"] = {
        "api_key": hash_key(os.getenv("DEFAULT_API_KEY", "test_api_key")),
        "permissions": ["read"],
        "rate_limit": "100/hour",
    }

    # Load additional keys from config or database
    # ...


def hash_key(key: str) -> str:
    """Hash API key for secure storage"""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(client_id: str, api_key: str) -> bool:
    """Verify API key for client"""
    if client_id not in API_KEYS:
        return False

    stored_hash = API_KEYS[client_id]["api_key"]
    provided_hash = hash_key(api_key)
    return hmac.compare_digest(stored_hash, provided_hash)


def require_api_key(f: Callable = None, permission: str | None = None):
    """
    Decorator to require API key authentication.
    Can be used as @require_api_key or @require_api_key("read").
    """

    def decorator(func: Callable):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            # Get API key from header or query param
            client_id = request.headers.get("X-Client-ID") or request.args.get("client_id")
            api_key = request.headers.get("X-API-Key") or request.args.get("api_key")

            if not client_id or not api_key:
                current_app.logger.warning(
                    f"Missing API key or client ID from {request.remote_addr}"
                )
                abort(401, description="API key and client ID are required")

            if not verify_api_key(client_id, api_key):
                current_app.logger.warning(f"Invalid API key from {client_id}")
                abort(401, description="Invalid API key")

            # Check permissions if specified
            if permission and permission not in API_KEYS[client_id]["permissions"]:
                current_app.logger.warning(f"Insufficient permissions for {client_id}")
                abort(
                    403,
                    description=f"This operation requires '{permission}' permission",
                )

            # Store client info in g for access in route
            g.client_id = client_id
            g.client_permissions = API_KEYS[client_id]["permissions"]

            return func(*args, **kwargs)

        return decorated_function

    # If called directly as @require_api_key without parentheses
    if f is not None and callable(f):
        return decorator(f)

    return decorator
