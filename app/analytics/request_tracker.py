# =============================================================================
# FILE: app/analytics/request_tracker.py
# DESCRIPTION: Request timing and analytics for API performance monitoring
# =============================================================================

import time
import uuid

from flask import current_app, g, request


def init_request_tracking(app):
    """Set up request tracking middleware"""

    @app.before_request
    def track_request_start():
        """Track the start time and generate a request ID"""
        g.start_time = time.time()
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def track_request_end(response):
        """Calculate request duration and log metrics"""
        # Skip tracking for static resources
        if request.path.startswith("/static"):
            return response

        # Calculate duration and convert to milliseconds
        duration_ms = int((time.time() - g.get("start_time", time.time())) * 1000)

        # Add request ID header to response
        response.headers["X-Request-ID"] = g.request_id

        # Log timing info
        endpoint = request.endpoint or "unknown"
        method = request.method
        path = request.path
        status_code = response.status_code

        # Log timing metrics
        current_app.logger.info(
            f"📊 REQUEST_TIMING: {method} {path} | "
            f"Status: {status_code} | Duration: {duration_ms}ms | "
            f"Endpoint: {endpoint} | Request ID: {g.request_id}"
        )

        # For API routes, record more detailed performance metrics
        if request.path.startswith("/api"):
            try:
                # In production, send to a metrics system like Prometheus
                record_api_metrics(
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    endpoint=endpoint,
                )
            except Exception as e:
                current_app.logger.error(f"Error recording API metrics: {e}")

        return response


def record_api_metrics(method: str, path: str, status_code: int, duration_ms: int, endpoint: str):
    """Record API metrics to monitoring system"""
    # Example implementation using a simple counter pattern
    # In production, use a proper metrics system

    # Create tags for metrics
    tags = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "endpoint": endpoint,
    }

    # Increment counters and histograms
    try:
        # Request count
        current_app.logger.info(f"📈 METRIC_INC: api_request_count | Tags: {tags}")

        # Latency histogram
        current_app.logger.info(
            f"📊 METRIC_HISTOGRAM: api_request_duration_ms | Value: {duration_ms} | Tags: {tags}"
        )

        # Status code counter
        status_category = status_code // 100
        current_app.logger.info(f"📈 METRIC_INC: api_status_{status_category}xx | Tags: {tags}")
    except Exception as e:
        # Ensure metric recording never breaks the app
        current_app.logger.error(f"Failed to record metrics: {e}")
