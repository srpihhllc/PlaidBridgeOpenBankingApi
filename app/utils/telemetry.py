# =============================================================================
# FILE: app/utils/telemetry.py
# DESCRIPTION: Cockpit-grade telemetry utilities providing counters, gauges,
#              histograms, structured event logging, TTL pulses, and safe
#              mock fallbacks for local/dev. Includes lifecycle events with
#              context-safety and optional Redis-based dedupe.
# =============================================================================
import functools
import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# --- Configuration & Global State ---
MOCK_MODE = os.getenv("TELEMETRY_MOCK_MODE", "True").lower() in ("true", "1", "t")
TTL_SUCCESS = int(os.getenv("TTL_SUCCESS_SECONDS", 300))
TTL_FAILURE = int(os.getenv("TTL_FAILURE_SECONDS", 600))
APP_ID = os.getenv("APP_ID", "default_app")

# Metric registry (mock)
_METRIC_LOOKUP: dict[str, "MockMetric"] = {}

# Prometheus/Redis availability flags (set below)
PROMETHEUS_CLIENT_ENABLED = False
_REDIS_AVAILABLE = False

# --- Conditional Imports (Prometheus / Redis) ---
if not MOCK_MODE:
    try:
        from prometheus_client import REGISTRY, Counter, Gauge, Histogram

        from app.utils.redis_utils import get_redis_client

        PROMETHEUS_CLIENT_ENABLED = True
        _REDIS_AVAILABLE = True
    except Exception as e:
        logger.warning(
            f"Failed to import prometheus_client/redis_utils: {e}. " "Falling back to MOCK_MODE."
        )
        MOCK_MODE = True
        PROMETHEUS_CLIENT_ENABLED = False
        _REDIS_AVAILABLE = False
else:
    # In mock mode we still want get_redis_client symbolically available for type-checkers,
    # but at runtime we will never call it when _REDIS_AVAILABLE is False.
    try:
        from app.utils.redis_utils import get_redis_client  # type: ignore[import]
    except Exception:  # pragma: no cover - purely defensive

        def get_redis_client():  # type: ignore[assignment]
            return None


# =============================================================================
# Mock Metric Implementation
# =============================================================================
class MockMetric:
    """Minimal mock metric compatible with common operations."""

    def __init__(
        self,
        name: str,
        description: str,
        mtype: str,
        labelnames: tuple | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.mtype = mtype
        self.labelnames = labelnames or ()
        self.value: float = 0.0
        self.samples: list[float] = []
        _METRIC_LOOKUP.setdefault(name, self)

    def inc(self, amount: float = 1, labels: dict[str, str] | None = None) -> None:
        if labels and set(labels.keys()) != set(self.labelnames):
            logger.warning(
                "MockMetric '%s': label mismatch. expected=%s provided=%s",
                self.name,
                self.labelnames,
                tuple(labels.keys()),
            )
        self.value += amount
        logger.debug(f"MOCK_METRIC INC {self.name} +{amount} labels={labels}")

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        if labels and set(labels.keys()) != set(self.labelnames):
            logger.warning(
                "MockMetric '%s': label mismatch. expected=%s provided=%s",
                self.name,
                self.labelnames,
                tuple(labels.keys()),
            )
        self.value = value
        logger.debug(f"MOCK_METRIC SET {self.name}={value} labels={labels}")

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        if labels and set(labels.keys()) != set(self.labelnames):
            logger.warning(
                "MockMetric '%s': label mismatch. expected=%s provided=%s",
                self.name,
                self.labelnames,
                tuple(labels.keys()),
            )
        self.samples.append(value)
        logger.debug(f"MOCK_METRIC OBSERVE {self.name}={value} labels={labels}")

    def labels(self, **labels: str) -> "MockMetric":
        return self

    def time(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Provide a decorator-compatible timing helper to mirror prometheus_client's .time().
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.perf_counter() - start
                    self.observe(duration)

            return wrapper

        return decorator


# =============================================================================
# Metric definitions
# =============================================================================
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)

if PROMETHEUS_CLIENT_ENABLED:
    _REQUEST_COUNTER = Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint"])
    _DB_FAILURE_COUNTER = Counter(
        "db_failure_count", "Database failures", ["error_type", "op_type"]
    )
    _IDENTITY_EVENT_COUNTER = Counter("identity_events_total", "Identity events", ["event_type"])
    _REDIS_HEALTH_GAUGE = Gauge("redis_health_status", "Redis health (1=up,0=down)", ["app_id"])
    _API_LATENCY_HISTOGRAM = Histogram(
        "http_request_duration_seconds",
        "HTTP Request latency",
        ["method", "endpoint"],
        buckets=_LATENCY_BUCKETS,
    )
    _HTTP_ERROR_404_COUNTER = Counter("http_error_404_v1", "HTTP 404 errors (v1)")
    _HTTP_ERROR_401_COUNTER = Counter("http_error_401_v1", "HTTP 401 errors (v1)")
    _METRIC_LOOKUP.update(
        {
            "http_requests_total": _REQUEST_COUNTER,
            "db_failure_count": _DB_FAILURE_COUNTER,
            "identity_events_total": _IDENTITY_EVENT_COUNTER,
            "redis_health_status": _REDIS_HEALTH_GAUGE,
            "http_request_duration_seconds": _API_LATENCY_HISTOGRAM,
            "http_error_404_v1": _HTTP_ERROR_404_COUNTER,
            "http_error_401_v1": _HTTP_ERROR_401_COUNTER,
        }
    )
else:
    _REQUEST_COUNTER = MockMetric(
        "http_requests_total", "Total HTTP Requests", "counter", ("method", "endpoint")
    )
    _DB_FAILURE_COUNTER = MockMetric(
        "db_failure_count", "Database failures", "counter", ("error_type", "op_type")
    )
    _IDENTITY_EVENT_COUNTER = MockMetric(
        "identity_events_total", "Identity events", "counter", ("event_type",)
    )
    _REDIS_HEALTH_GAUGE = MockMetric("redis_health_status", "Redis health", "gauge", ("app_id",))
    _API_LATENCY_HISTOGRAM = MockMetric(
        "http_request_duration_seconds",
        "HTTP latency",
        "histogram",
        ("method", "endpoint"),
    )
    _HTTP_ERROR_404_COUNTER = MockMetric("http_error_404_v1", "HTTP 404 errors (v1)", "counter")
    _HTTP_ERROR_401_COUNTER = MockMetric("http_error_401_v1", "HTTP 401 errors (v1)", "counter")

_METRIC_LOOKUP.setdefault("http_requests_total", _REQUEST_COUNTER)
_METRIC_LOOKUP.setdefault("db_failure_count", _DB_FAILURE_COUNTER)
_METRIC_LOOKUP.setdefault("identity_events_total", _IDENTITY_EVENT_COUNTER)
_METRIC_LOOKUP.setdefault("redis_health_status", _REDIS_HEALTH_GAUGE)
_METRIC_LOOKUP.setdefault("http_request_duration_seconds", _API_LATENCY_HISTOGRAM)
_METRIC_LOOKUP.setdefault("http_error_404_v1", _HTTP_ERROR_404_COUNTER)
_METRIC_LOOKUP.setdefault("http_error_401_v1", _HTTP_ERROR_401_COUNTER)


# =============================================================================
# Metric helpers
# =============================================================================
def _get_metric(name: str) -> Any | None:
    if MOCK_MODE:
        return _METRIC_LOOKUP.get(name)
    try:
        # REGISTRY is only available when PROMETHEUS_CLIENT_ENABLED is True
        return (
            REGISTRY._names_to_collectors.get(name)
            if PROMETHEUS_CLIENT_ENABLED
            else _METRIC_LOOKUP.get(name)
        )
    except Exception:
        return _METRIC_LOOKUP.get(name)


def inc_metric(name: str, labels: dict[str, str] | None = None, amount: float = 1) -> None:
    metric = _get_metric(name)
    if not metric:
        logger.warning(f"inc_metric: unknown metric '{name}'")
        return
    try:
        if labels:
            metric.labels(**labels).inc(amount)
        else:
            metric.inc(amount)
    except Exception as e:
        logger.debug(f"inc_metric fallback for '{name}': {e}")


def set_metric(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    metric = _get_metric(name)
    if not metric or not hasattr(metric, "set"):
        logger.warning(f"set_metric: unknown or non-gauge metric '{name}'")
        return
    try:
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)
    except Exception as e:
        logger.debug(f"set_metric fallback for '{name}': {e}")


def record_timing_sample(
    name: str, duration_seconds: float, labels: dict[str, str] | None = None
) -> None:
    metric = _get_metric(name)
    if not metric or not hasattr(metric, "observe"):
        logger.warning(f"record_timing_sample: unknown or non-histogram metric '{name}'")
        return
    try:
        if labels:
            metric.labels(**labels).observe(duration_seconds)
        else:
            metric.observe(duration_seconds)
    except Exception as e:
        logger.debug(f"record_timing_sample fallback for '{name}': {e}")


F = TypeVar("F", bound=Callable[..., Any])


def time_metric(name: str, labels: dict[str, str] | None = None) -> Callable[[F], F]:
    """
    Decorator factory that records timing samples for the wrapped function.
    If the underlying metric exposes a .time() decorator (e.g. Prometheus),
    we delegate to it; otherwise we use a generic wrapper.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                record_timing_sample(name, duration, labels)
                logger.debug(f"time_metric: {name}={duration:.4f}s labels={labels}")

        return wrapper  # type: ignore[return-value]

    metric = _get_metric(name)
    if metric and hasattr(metric, "time"):
        try:
            # Prometheus Histogram/Timer exposes .time() as a decorator/context manager.
            return metric.time()  # type: ignore[no-any-return]
        except Exception:
            pass
    return decorator


# =============================================================================
# TTL pulses and failures
# =============================================================================
def ttl_pulse_emit(
    key: str, status: str, ttl_seconds: int, meta: dict[str, Any] | None = None
) -> None:
    payload = {
        "status": status,
        "timestamp": time.time(),
        "meta": meta or {},
        "source": "telemetry",
        "app_id": APP_ID,
    }
    if MOCK_MODE or not _REDIS_AVAILABLE:
        logger.info(
            "TTL_EMIT (Mock): %s status=%s ttl=%ss payload=%s",
            key,
            status,
            ttl_seconds,
            json.dumps(payload),
        )
        return
    try:
        redis = get_redis_client()
        if redis is None:
            logger.error("TTL_EMIT: Redis client is None; skipping emit.")
            return
        try:
            redis.setex(key, ttl_seconds, json.dumps(payload))
        except TypeError:
            # fallback for clients that use different signature
            redis.set(key, json.dumps(payload), ex=ttl_seconds)
        logger.debug(f"TTL_EMIT (Redis): {key} ttl={ttl_seconds}s")
    except Exception as e:
        logger.error(f"CRITICAL: TTL emit failed for key '{key}': {e}")
        try:
            set_metric("redis_health_status", 0, labels={"app_id": APP_ID})
        except Exception:
            pass


def log_db_failure(
    context: str,
    error: Exception,
    op_type: str = "query",
    error_type: str = "operational",
) -> None:
    msg = str(error)
    logger.error(f"DB Failure in {context} ({op_type}): {error_type} {msg}")
    try:
        inc_metric("db_failure_count", labels={"error_type": error_type, "op_type": op_type})
    except Exception:
        pass
    structured = {
        "event_type": "db_failure",
        "context": context,
        "op_type": op_type,
        "error_type": error_type,
        "error_detail": msg,
        "timestamp": datetime.now(UTC).isoformat(),
        "app_id": APP_ID,
    }
    logger.critical(json.dumps(structured))
    ttl_pulse_emit(
        f"ttl_pulse:db_failure:{APP_ID}:{context.replace('/', '_')}",
        "FAILURE",
        TTL_FAILURE,
        meta={"context": context},
    )


# =============================================================================
# Identity events
# =============================================================================
def log_identity_event(
    user_id: Any | None,
    event_type: str,
    ip: str | None = None,
    user_agent: str | None = None,
    details: Any | None = None,
) -> None:
    try:
        inc_metric("identity_events_total", labels={"event_type": event_type})
    except Exception:
        pass

    meta = {"ip": ip, "user_agent": user_agent, "details": details}

    event = {
        "event_type": event_type,
        "user_id": user_id if user_id is not None else "system",
        "timestamp": datetime.now(UTC).isoformat(),
        "meta": meta,
        "app_id": APP_ID,
    }

    if MOCK_MODE or not _REDIS_AVAILABLE:
        logger.info(f"Identity Event (Mock): {json.dumps(event)}")
        return

    try:
        redis = get_redis_client()
        if redis is None:
            logger.error("Identity event: Redis client is None; skipping stream push.")
            return
        redis.lpush("identity_events_stream", json.dumps(event))
        try:
            redis.ltrim("identity_events_stream", 0, 4999)
        except Exception:
            # Some redis clients may not implement ltrim in the same way; ignore if unavailable
            pass
        ttl_pulse_emit(
            f"ttl_pulse:identity_activity:{APP_ID}",
            "SUCCESS",
            TTL_SUCCESS,
            meta={"last_event": event_type},
        )
        logger.debug(f"Identity event logged: {event_type}")
    except Exception as e:
        logger.error(f"CRITICAL: Identity event stream failure: {e}")
        ttl_pulse_emit(f"ttl_pulse:telemetry_failure:{APP_ID}", "FAILURE", TTL_FAILURE)


def record_lifecycle_event(
    event_type: str = "restart",
    dedupe_window_seconds: int = 5,
    require_app_context: bool = False,
) -> None:
    # ---------------------------------------------------------
    # Skip lifecycle telemetry entirely during tests
    # ---------------------------------------------------------
    if (
        os.getenv("FLASK_ENV") == "testing"
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
    ):
        return

    evt = (event_type or "restart").lower()
    if evt not in ("restart", "shutdown"):
        logger.warning(
            "record_lifecycle_event: unknown event_type '%s', defaulting to 'restart'",
            event_type,
        )
        evt = "restart"

    try:
        from flask import current_app
    except Exception:
        current_app = None

    if require_app_context and not current_app:
        raise RuntimeError("record_lifecycle_event requires an active Flask app context")

    did_push = False
    try:
        if not current_app:
            try:
                from app import create_app as _create_app

                _app = _create_app()
                _app.app_context().push()
                did_push = True
            except Exception:
                logger.debug(
                    "record_lifecycle_event: could not push temporary app context; "
                    "proceeding without it"
                )

        context = "system_startup" if evt == "restart" else "system_shutdown"
        ttl_key = f"ttl_pulse:system_event:{evt}:{APP_ID}"
        dedupe_key = f"{ttl_key}:dedupe"

        if not MOCK_MODE and _REDIS_AVAILABLE:
            try:
                redis = get_redis_client()
                if redis:
                    was_set = redis.set(
                        dedupe_key,
                        str(os.getpid()),
                        nx=True,
                        ex=dedupe_window_seconds,
                    )
                    if not was_set:
                        return
            except Exception:
                pass

        ttl_pulse_emit(
            ttl_key,
            "SUCCESS",
            TTL_SUCCESS,
            meta={"event_type": evt, "context": context},
        )

        structured = {
            "event_type": f"system_{evt}",
            "app_id": APP_ID,
            "timestamp": datetime.now(UTC).isoformat(),
            "message": f"Application worker {evt} detected.",
            "context": context,
            "pid": os.getpid(),
        }
        logger.critical(json.dumps(structured))
        logger.info(f"✅ {evt.capitalize()} telemetry event recorded.")
    finally:
        if did_push:
            try:
                from flask import _app_ctx_stack

                _app_ctx_stack.pop()
            except Exception:
                pass


# Backwards-compatible alias expected by WSGI
def record_restart_event(event_type: str = "restart") -> None:
    record_lifecycle_event(event_type)


# =============================================================================
# Operational decorator: pulse_on_completion
# =============================================================================
def pulse_on_completion(key_prefix: str, op_type: str = "job") -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            context = f"{func.__module__}.{func.__name__}"
            try:
                result = func(*args, **kwargs)
                ttl_pulse_emit(
                    f"ttl_pulse:{key_prefix}:success:{APP_ID}",
                    "SUCCESS",
                    TTL_SUCCESS,
                    meta={"context": context, "op_type": op_type},
                )
                return result
            except Exception as e:
                log_db_failure(
                    context=context,
                    error=e,
                    op_type=op_type,
                    error_type=e.__class__.__name__,
                )
                raise

        return wrapper

    return decorator


# =============================================================================
# Deprecated shims (kept for migration)
# =============================================================================
def increment_counter(name: str, value: float = 1, labels: dict[str, str] | None = None) -> None:
    logger.warning(
        "[Telemetry Shim] increment_counter is deprecated. Use inc_metric('%s') instead.",
        name,
    )
    inc_metric(name, labels=labels, amount=value)


def increment_timing(
    name: str, description: str = "Timing shim", labels: dict[str, str] | None = None
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.warning(
                "[Telemetry Shim] increment_timing is deprecated. Use @time_metric('%s') "
                "instead.",
                name,
            )
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                record_timing_sample(name, duration, labels)
                logger.info(f"TIMING SHIM: {name} executed in {duration:.4f}s")

        return wrapper

    return decorator


def log_route_usage(method: str, endpoint: str) -> None:
    logger.warning(
        "DEPRECATED: log_route_usage shim. Migrate to inc_metric('http_requests_total', ...)."
    )
    try:
        _REQUEST_COUNTER.labels(method=method, endpoint=endpoint).inc()
    except Exception:
        try:
            inc_metric("http_requests_total", labels={"method": method, "endpoint": endpoint})
        except Exception:
            pass


def time_route_latency(method: str, endpoint: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                try:
                    _API_LATENCY_HISTOGRAM.labels(method=method, endpoint=endpoint).observe(
                        duration
                    )
                except Exception:
                    try:
                        record_timing_sample(
                            "http_request_duration_seconds",
                            duration,
                            labels={"method": method, "endpoint": endpoint},
                        )
                    except Exception:
                        pass

        return wrapper

    return decorator


# =============================================================================
# Convenience decorator: route-level metrics + logging
# =============================================================================
def log_route(route_path: str) -> Callable[[F], F]:
    def decorator(f: F) -> F:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            method = "GET"
            try:
                from flask import request

                method = request.method
            except Exception:
                pass
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                try:
                    inc_metric(
                        "http_requests_total",
                        labels={"method": method, "endpoint": route_path},
                    )
                    record_timing_sample(
                        "http_request_duration_seconds",
                        duration,
                        labels={"method": method, "endpoint": route_path},
                    )
                except Exception:
                    logger.debug("log_route: metric recording failed.")
                logger.debug(f"ROUTE_USAGE: {method} {route_path} completed in {duration:.4f}s")

        return wrapper

    return decorator


# =============================================================================
# Telemetry lifecycle hooks expected by app/__init__.py
# =============================================================================
def add_telemetry_hooks(app):
    """
    Attach request-level telemetry hooks.
    Placeholder implementation to satisfy imports and maintain architecture.
    """
    return


def record_app_start(app):
    """
    Emit a startup lifecycle event.
    Placeholder implementation that uses existing lifecycle primitives.
    """
    try:
        record_lifecycle_event("restart")
    except Exception:
        pass
    return


def register_cli_teardown(app):
    """
    Register teardown handlers for CLI commands.
    Placeholder implementation that emits shutdown lifecycle events.
    """

    @app.teardown_appcontext
    def _teardown(exc):
        try:
            record_lifecycle_event("shutdown")
        except Exception:
            pass
        return


def _get_safe_redis_client():
    """
    Safely retrieves a Redis client, returning None if connection fails.
    Used for TTL pulse emission and non-critical telemetry.
    """
    import os

    try:
        import redis

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        # Test connection
        client.ping()
        return client
    except Exception:
        # Fail silently - Redis is optional for telemetry
        return None
