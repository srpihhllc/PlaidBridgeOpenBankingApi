# =============================================================================
# FILE: app/middleware/response_wrapper.py
# DESCRIPTION: Middleware for standardizing API responses
# =============================================================================

import time

from flask import g, jsonify, request


def init_response_handling(app):
    """Initialize response handling middleware"""

    @app.before_request
    def before_request():
        """Set start time for request timing"""
        g.start_time = time.time()

    @app.after_request
    def standardize_response(response):
        """Wrap all JSON responses in standard envelope"""

        # Skip non-JSON responses
        if not response.content_type.startswith("application/json"):
            return response

        # Only wrap API responses
        if not request.path.startswith("/api"):
            return response

        # Get original data
        try:
            data = response.get_json()
        except Exception:
            # If response isn't JSON, return it as-is
            return response

        # If already using our standard format, return as-is
        if isinstance(data, dict) and "status" in data and ("data" in data or "code" in data):
            return response

        # Calculate request duration
        duration_ms = int((time.time() - g.get("start_time", time.time())) * 1000)

        # Create standard response envelope
        if response.status_code >= 400:
            standard_response = {
                "status": "error",
                "code": f"HTTP_{response.status_code}",
                "message": data.get("message", "An error occurred"),
                "request_id": getattr(g, "request_id", None),
                "meta": {"duration_ms": duration_ms},
            }
        else:
            standard_response = {
                "status": "success",
                "message": data.get("message", "Success"),
                "data": data,
                "request_id": getattr(g, "request_id", None),
                "meta": {"duration_ms": duration_ms},
            }

        # Create new response with our standardized format
        new_response = jsonify(standard_response)
        new_response.status_code = response.status_code

        # Copy headers from original response
        for key, value in response.headers.items():
            if key != "Content-Length":
                new_response.headers[key] = value

        return new_response
