# =============================================================================
# FILE: app/utils/api_response.py
# DESCRIPTION: Centralized response utility helpers for consistent JSON output.
#              This ensures all API versions (v1, generic root) use the same
#              schema, preventing response divergence.
# =============================================================================
import logging
from typing import Any

from flask import Response, g, jsonify

logger = logging.getLogger(__name__)


def format_response(
    status: str,
    message: str,
    data: dict[str, Any] | None = None,
    version: str = "generic",
    error_code: str | None = None,
    http_status_code: int = 200,
) -> tuple[Response, int]:
    """
    Formats a consistent JSON response object.

    :param status: "success" or "error"
    :param message: A human-readable message.
    :param data: The primary payload (for success responses).
    :param version: The API version ('generic' or 'v1').
    :param error_code: A machine-readable error code (for error responses).
    :param http_status_code: The HTTP status code to return.
    :return: A tuple of (Flask Response, HTTP Status Code).
    """
    response_payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "version": version,
        "timestamp": (
            g.request_start_time.isoformat() if hasattr(g, "request_start_time") else None
        ),
        # Request ID is injected by middleware in app/__init__.py
        "request_id": getattr(g, "request_id", "unknown"),
    }

    if status == "success":
        response_payload["data"] = data if data is not None else {}
    elif status == "error":
        response_payload["error_code"] = error_code if error_code else "E_UNKNOWN"

    # Log the full error response for debugging
    if status == "error":
        logger.warning(
            "API Error [%s] - Status: %d, Code: %s, Message: %s, Data: %s",
            response_payload["request_id"],
            http_status_code,
            response_payload.get("error_code"),
            message,
            data,
        )

    return jsonify(response_payload), http_status_code


def success_response(
    data: dict[str, Any] | None = None,
    message: str = "Request successful.",
    version: str = "generic",
    http_status_code: int = 200,
) -> tuple[Response, int]:
    """Generates a success API response."""
    return format_response(
        status="success",
        message=message,
        data=data,
        version=version,
        http_status_code=http_status_code,
    )


def error_response(
    error_code: str,
    message: str,
    version: str = "generic",
    http_status_code: int = 400,
    data: dict[str, Any] | None = None,
) -> tuple[Response, int]:
    """Generates an error API response."""
    return format_response(
        status="error",
        message=message,
        data=data,
        version=version,
        error_code=error_code,
        http_status_code=http_status_code,
    )
