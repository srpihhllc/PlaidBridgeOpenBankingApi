# app/utils/security_utils.py
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
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urljoin

from flask import g, jsonify, request

_logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Request ID + timing instrumentation
# -----------------------------------------------------------------------------
# NOTE: Use 12 hex characters for request_id to match other parts of the app
# (e.g. correlation IDs created elsewhere use uuid.uuid4().hex[:12]).
_REQUEST_ID_LENGTH = 12


def inject_request_id(app=None) -> None:
    """
    Attach request_id and timing to every request for traceability.

    Behavior:
      - If called with an app argument, registers this function as a before_
        request hook and registers finalize_request_logging as an after_request
        hook.
      - If called without arguments (Flask invoking it as a before_request
        hook), it sets g.request_id and g.start_time and logs the START event.
    """
    if app is not None:
        app.before_request(inject_request_id)
        app.after_request(finalize_request_logging)
        return

    try:
        g.request_id = uuid.uuid4().hex[:_REQUEST_ID_LENGTH]
        g.start_time = time.time()
        _logger.info(
            f"START Request request_id={g.request_id}",
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


def finalize_request_logging(response):
    """
    After-request hook to log request completion with duration and status code.
    """
    try:
        duration_ms = (
            (time.time() - g.start_time) * 1000
            if hasattr(g, "start_time")
            else -1
        )
        _logger.info(
            "END Request"
            f" request_id={get_request_id()}"
            f" status={getattr(response, 'status_code', None)}"
            f" duration_ms={round(duration_ms, 2)}",
            extra={
                "request_id": get_request_id(),
                "status_code": getattr(response, "status_code", None),
                "duration_ms": round(duration_ms, 2),
            },
        )
    except Exception as exc:
        _logger.exception("Failed to finalize request logging: %s", exc)
    return response


def get_request_id() -> str:
    """Retrieve the current request_id, defaulting to 'N/A'."""
    return getattr(g, "request_id", "N/A")


# -----------------------------------------------------------------------------
# Uniform JSON response envelopes
# -----------------------------------------------------------------------------
def success_response(
    data: Optional[Dict[str, Any]] = None,
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
    data: Optional[Dict[str, Any]] = None,
):
    envelope = {
        "status": "error",
        "error": {"code": code, "message": message},
        "data": data or {},
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": get_request_id(),
        },
    }
    return jsonify(envelope), http_status_code


# -----------------------------------------------------------------------------
# MFA logging utilities
# -----------------------------------------------------------------------------
def log_mfa_attempt(user, method: str, expiration: Optional[datetime]) -> None:
    """
    Log MFA attempts without exposing the actual MFA code.
    Includes user_id, method, and expiration timestamp.

    The formatted message intentionally includes the method (e.g. "sms") so
    operators and tests can find it in rec.getMessage(). Sensitive MFA codes
    are never included in the message.
    """
    try:
        _logger.info(
            f"MFA code generated method={method}",
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


# -----------------------------------------------------------------------------
# Deterministic PII hashing
# -----------------------------------------------------------------------------
def hash_pii_for_key(value: str) -> str:
    """
    Deterministically hash sensitive values (like email) into a SHA256 hex
    string. Used for Redis keys and telemetry identifiers.
    """
    if not value:
        return "EMPTY"
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# URL safety helper (prevents open redirects)
# -----------------------------------------------------------------------------
def is_safe_url(target: str) -> bool:
    """
    Prevent open redirects by ensuring the target URL stays within this host.
    """
    try:
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return (
            test_url.scheme in ("http", "https")
            and ref_url.netloc == test_url.netloc
        )
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Optional: logging filter to ensure request_id exists on LogRecord objects.
# Call attach_request_id_log_filter() from app startup if desired.
# -----------------------------------------------------------------------------
class _RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            try:
                record.request_id = get_request_id()
            except Exception:
                record.request_id = "N/A"
        if not hasattr(record, "duration_ms"):
            record.duration_ms = None
        return True


def attach_request_id_log_filter(logger: Optional[logging.Logger] = None) -> None:
    """
    Add a RequestId filter to the given logger (or root logger) so formatters
    can reference %(request_id)s without KeyError.
    """
    lg = logger or logging.getLogger()
    if not any(isinstance(f, _RequestIdFilter) for f in lg.filters):
        lg.addFilter(_RequestIdFilter())