# =============================================================================
# FILE: app/utils/security_utils.py
# DESCRIPTION: Cross-cutting utilities for security, telemetry, and uniform
#              response schema. Provides request IDs, MFA-safe logging, and
#              cockpit-grade JSON envelopes for all API routes.
# =============================================================================

import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from flask import g, jsonify, request

_logger = logging.getLogger(__name__)


# ✅ FIX: Redefine inject_request_id as a no-argument before_request hook
def inject_request_id() -> None:
    """
    Attach request_id and timing to every request for traceability.
    - Generates a short UUID for each request.
    - Logs start and end with duration and status code.
    - Ensures request_id is always available via get_request_id().
    """
    try:
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()
        _logger.info(
            "START Request",
            extra={
                "request_id": g.request_id,
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "user_agent": str(request.user_agent),
            },
        )
    except Exception as exc:
        _logger.exception("Failed to initialize request_id: %s", exc)
        g.request_id = "N/A"
        g.start_time = time.time()


# ✅ FIX: Add an after_request hook to finalize logging
def finalize_request_logging(response):
    """
    After-request hook to log request completion with duration and status code.
    """
    try:
        duration_ms = (time.time() - g.start_time) * 1000 if hasattr(g, "start_time") else -1
        _logger.info(
            "END Request",
            extra={
                "request_id": getattr(g, "request_id", "N/A"),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
    except Exception as exc:
        _logger.exception("Failed to finalize request logging: %s", exc)
    return response


def get_request_id() -> str:
    """Retrieve the current request_id, defaulting to 'N/A'."""
    return getattr(g, "request_id", "N/A")


def success_response(
    data: dict[str, Any] | None = None,
    message: str = "Success",
    http_status_code: int = 200,
):
    envelope = {
        "status": "success",
        "data": data or {},
        "message": message,
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": get_request_id(),
        },
    }
    return jsonify(envelope), http_status_code


def error_response(
    code: str,
    message: str = "An error occurred",
    http_status_code: int = 400,
    data: dict[str, Any] | None = None,
):
    envelope = {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        "data": data or {},
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": get_request_id(),
        },
    }
    return jsonify(envelope), http_status_code


def log_mfa_attempt(user, method: str, expiration: datetime | None) -> None:
    """
    Log MFA attempts without exposing the actual MFA code.
    Includes user_id, method, and expiration timestamp.
    """
    try:
        _logger.info(
            "MFA code generated",
            extra={
                "user_id": getattr(user, "id", None),
                "email": getattr(user, "email", None),
                "method": method,
                "expires_at": expiration.isoformat() if expiration else None,
                "request_id": get_request_id(),
            },
        )
    except Exception as exc:
        _logger.exception("Failed to log MFA attempt: %s", exc)


def hash_pii_for_key(value: str) -> str:
    """
    Deterministically hash sensitive values (like email) into a SHA256 hex string.
    Used for Redis keys and telemetry identifiers to avoid leaking raw PII.
    """
    if not value:
        return "EMPTY"
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()
