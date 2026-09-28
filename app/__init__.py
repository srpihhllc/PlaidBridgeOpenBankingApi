# =============================================================================
# FILE: app/__init__.py
# DESCRIPTION: Unified, hardened, cockpit-grade Flask application factory.
#                Single authoritative blueprint registration path, single
#                authoritative url_map rebuild, defensive guards to avoid
#                double-registration and preserve admin UI aliases.
# =============================================================================

import importlib
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import Blueprint, Flask, Response, current_app, g, jsonify, request
from flask_apscheduler import APScheduler
from sqlalchemy import inspect, text
from werkzeug.exceptions import BadRequest, HTTPException

from app.blueprints import register_blueprints, validate_blueprints_graph
from app.blueprints.admin_ui_routes import ensure_admin_aliases
from app.cli import register_cli_commands
from app.config import CONFIG_MAP, get_config_class
from app.extensions import db, init_extensions, socketio
from app.routes.treasury_routes import treasury_bp
from app.tracing import handle_traced_error
from app.webhooks.views import webhooks

_logger = logging.getLogger(__name__)

# Instantiate the scheduler extension
scheduler = APScheduler()

# ---------------------------------------------------------------------------
# Configuration: conservative defaults and test-friendly hooks
# ---------------------------------------------------------------------------
DEFAULT_ALLOW_PREMATURE_CLEANUP = True

ROUTE_PRUNE_WHITELIST: Set[str] = {
    "oauth.callback_google",
    "oauth.callback_google_clean",
    "oauth.callback_provider",
    "oauth.callback_provider_legacy",
    "healthz",
    "readyz",
    "version",
    "diagnostics",
    "dependency_graph",
    "metrics",
    "admin.admin_index",
}

_maybe_redis_client: Any | None = None

# =============================================================================
# Public Helper Functions
# =============================================================================


def add_route_prune_whitelist(endpoint: str) -> Set[str]:
    """Add an endpoint to the route pruning whitelist dynamically."""
    if endpoint:
        ROUTE_PRUNE_WHITELIST.add(endpoint)
    return ROUTE_PRUNE_WHITELIST


# =============================================================================
# Internal helpers
# =============================================================================


def _ensure_admin_index_registered(app: Any) -> None:
    """
    Normalize the admin index rule after blueprint registration.

    This is intentionally defensive because it is called during factory
    initialization and may also receive lightweight test doubles.
    """
    try:
        url_map = getattr(app, "url_map", None)
        if url_map is None:
            return None

        rules_by_endpoint = getattr(url_map, "_rules_by_endpoint", None)
        if not isinstance(rules_by_endpoint, dict):
            return None

        endpoint = "admin.admin_index"
        rules = rules_by_endpoint.get(endpoint)

        if not rules:
            return None

        # Preserve order while removing duplicate rule objects.
        unique_rules = []
        seen = set()

        for rule in rules:
            marker = id(rule)

            if marker in seen:
                continue

            seen.add(marker)
            unique_rules.append(rule)

        rules_by_endpoint[endpoint] = unique_rules

    except Exception:
        # Route hygiene must never prevent application startup.
        return None

    return None


def _safe_status_code(code: Any) -> int:
    try:
        return int(code)
    except Exception:
        return 500


def _replace_url_map_rules(
    flask_app: Flask,
    rules: List[Any],
    rules_by_endpoint: Dict[str, List[Any]],
) -> None:
    """Centralized helper for mutating Flask url_map internals safely across Werkzeug versions."""
    try:
        if hasattr(flask_app.url_map, "_rules"):
            try:
                flask_app.url_map._rules = rules
            except AttributeError:
                rules_attr = getattr(flask_app.url_map, "_rules", None)
                if isinstance(rules_attr, list):
                    rules_attr.clear()
                    rules_attr.extend(rules)

        flask_app.url_map._rules_by_endpoint = rules_by_endpoint
    except Exception:
        flask_app.logger.debug("_replace_url_map_rules failed", exc_info=True)


def _register_blueprints(flask_app: Flask) -> None:
    """
    Auto-discovery blueprint loader with duplicate registration guards.
    Temporarily wraps Flask.register_blueprint to skip already-registered
    blueprint names. Restores original method immediately after.
    """
    try:
        _original_register_blueprint = flask_app.register_blueprint

        def _guarded_register_blueprint(
            bp: Blueprint | Any, **options: Any
        ) -> Any:
            bp_name = getattr(bp, "name", None)

            # Catch both string checking and existing instance names globally
            if bp_name and (
                bp_name in flask_app.blueprints
                or bp_name in flask_app.blueprints.keys()
            ):
                flask_app.logger.debug(
                    "Auto-discovery: blueprint '%s' already registered "
                    "globally; skipping.",
                    bp_name,
                )
                return None

            return _original_register_blueprint(bp, **options)

        flask_app.register_blueprint = (  # type: ignore[method-assign]
            _guarded_register_blueprint  # type: ignore[assignment]
        )
        try:
            register_blueprints(flask_app)
            validate_blueprints_graph(flask_app)
            flask_app.logger.info("All blueprints registered successfully.")
        finally:
            flask_app.register_blueprint = (  # type: ignore[method-assign]
                _original_register_blueprint
            )

    except Exception as exc:
        flask_app.logger.error(
            "❌ Blueprint auto-registration failed: %s", exc, exc_info=True
        )
        raise


def _register_cli_commands(flask_app: Flask) -> None:
    """
    Register top-level CLI commands onto the Flask application.
    Executes the authoritative entrypoint in app.cli_top_level and app.cli.health_check.
    """
    try:
        from app.cli.health_check import health_check
        flask_app.cli.add_command(health_check)
    except Exception as exc:
        flask_app.logger.warning(
            "Failed to register health_check CLI command: %s", exc, exc_info=True
        )

    try:
        import app.cli_top_level as cli_module

        if hasattr(cli_module, "register_cli_commands"):
            cli_module.register_cli_commands(flask_app)
        elif hasattr(cli_module, "init_app"):
            cli_module.init_app(flask_app)
        else:
            flask_app.logger.warning("No registration function found in app.cli_top_level.")

    except Exception as exc:
        flask_app.logger.warning(
            "Failed to register top-level CLI commands: %s", exc, exc_info=True
        )


# =============================================================================
# Error handlers
# =============================================================================
def _register_error_handlers(flask_app: Flask) -> None:
    def _handle_exception(e: Exception) -> Any:
        # --- Interactive Error Tracing ---
        try:
            handle_traced_error(e)
        except Exception:
            pass

        # --- Diagnostic crash dump ---
        try:
            import traceback

            filepath = (
                "/home/srpihhllc/PlaidBridgeOpenBankingApi/"
                "forced_crash_dump.txt"
            )
            try:
                with open(filepath, "a") as f:
                    f.write(
                        f"\n=== CRASH CAPTURED AT "
                        f"{datetime.now(timezone.utc).isoformat()} ===\n"
                    )
                    try:
                        f.write(f"URL: {request.url}\n")
                        f.write(f"Method: {request.method}\n")
                        f.write(f"Endpoint: {request.endpoint}\n")
                    except Exception:
                        f.write("Request context unavailable or partial\n")
                    traceback.print_exc(file=f)
                    f.write("=" * 60 + "\n")
            except Exception:
                pass
        except Exception:
            pass

        # --- Standard HTTP error handling logic ---
        if isinstance(e, HTTPException):
            status = _safe_status_code(getattr(e, "code", 500))
            description = getattr(e, "description", str(e))
            name = getattr(e, "name", "HTTPException")
        else:
            status = 500
            description = str(e)
            name = type(e).__name__

        if status == 400 and isinstance(e, BadRequest):
            if request.endpoint == "main.ignite_cortex":
                return e

            import traceback as _tb

            _logger.error("BADREQUEST_PROBE: %s", _tb.format_exc())
            status = 422
            description = "Request body must be valid JSON"
            name = "Unprocessable Entity"

        if flask_app.config.get("ENV") == "production" and status >= 500:
            description = "The server encountered an internal error."
            name = "Internal Server Error"

        _logger.log(
            logging.WARNING if status < 500 else logging.ERROR,
            "HTTP %s (%s): %s",
            status,
            name,
            description,
        )

        resp = jsonify({"msg": name, "error": description})
        resp.status_code = status
        return resp

    for code in (400, 401, 403, 404, 422, 500, 503):
        flask_app.register_error_handler(code, _handle_exception)

    flask_app.register_error_handler(HTTPException, _handle_exception)
    flask_app.register_error_handler(Exception, _handle_exception)


# =============================================================================
# Database initialization
# =============================================================================
def _ensure_db_tables(flask_app: Flask) -> None:
    """Deterministic DB initialization ensuring essential tables exist."""
    if flask_app.config.get("TESTING"):
        try:
            importlib.import_module("app.models")
            with flask_app.app_context():
                db.create_all()
        except Exception as exc:
            _logger.exception("db.create_all() failed in TESTING: %s", exc)
        return

    try:
        with flask_app.app_context():
            inspector = inspect(db.engine)
            existing = set(inspector.get_table_names() or [])
    except Exception as exc:
        _logger.exception("Failed to inspect DB schema: %s", exc)
        return

    essential = {"users", "trace_events"}
    if essential.issubset(existing):
        return

    if os.getenv("ALEMBIC_RUNNING", "0") == "1":
        _logger.debug("ALEMBIC_RUNNING=1; skipping db.create_all()")
        return

    try:
        importlib.import_module("app.models")
        with flask_app.app_context():
            db.create_all()
    except Exception as exc:
        _logger.exception("db.create_all() failed in NON-TESTING: %s", exc)


# =============================================================================
# Healthcheck registry + factories
# =============================================================================

HealthCheckResult = Dict[str, Any]
HealthCheckFn = Callable[[], HealthCheckResult]


class HealthCheckRegistry:
    def __init__(self) -> None:
        self._checks: Dict[str, HealthCheckFn] = {}

    def register(self, name: str, fn: HealthCheckFn) -> None:
        if not callable(fn):
            raise TypeError("healthcheck must be callable")

        self._checks[name] = fn
        _logger.debug("Health check registered: %s", name)

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)
        _logger.debug("Health check unregistered: %s", name)

    def run_check(self, name: str) -> HealthCheckResult:
        fn = self._checks.get(name)

        if fn is None:
            return {
                "ok": False,
                "error": "not_registered",
            }

        try:
            result = fn()

            if not isinstance(result, dict):
                return {
                    "ok": False,
                    "error": "invalid_result_type",
                }

            normalized = dict(result)
            normalized["ok"] = bool(normalized.get("ok", False))

            return normalized

        except Exception as exc:
            _logger.debug(
                "Health check '%s' raised: %s",
                name,
                exc,
                exc_info=True,
            )

            return {
                "ok": False,
                "error": str(exc),
            }

    def run_all(self) -> Dict[str, HealthCheckResult]:
        return {
            name: self.run_check(name)
            for name in sorted(self._checks)
        }

    def list_checks(self) -> Tuple[str, ...]:
        return tuple(sorted(self._checks))


_registry = HealthCheckRegistry()


def register_healthcheck(name: str, fn: HealthCheckFn) -> None:
    _registry.register(name, fn)


def unregister_healthcheck(name: str) -> None:
    _registry.unregister(name)


def _make_db_check() -> HealthCheckFn:
    def _db_check() -> HealthCheckResult:
        start = time.time()

        try:
            db.session.execute(text("SELECT 1"))
            latency_ms = (time.time() - start) * 1000.0

            return {
                "ok": True,
                "latency_ms": round(latency_ms, 2),
            }

        except Exception as exc:
            latency_ms = (time.time() - start) * 1000.0

            return {
                "ok": False,
                "error": str(exc),
                "latency_ms": round(latency_ms, 2),
            }

    return _db_check


def _make_redis_check() -> HealthCheckFn:
    def _redis_check() -> HealthCheckResult:
        start = time.time()

        try:
            redis_client = (
                getattr(current_app, "redis_client", None)
                or _maybe_redis_client
            )

            if not redis_client:
                return {
                    "ok": False,
                    "error": "no_client",
                    "latency_ms": 0.0,
                }

            pong = (
                redis_client.ping()
                if hasattr(redis_client, "ping")
                else True
            )

            latency_ms = (time.time() - start) * 1000.0

            return {
                "ok": bool(pong),
                "latency_ms": round(latency_ms, 2),
            }

        except Exception as exc:
            latency_ms = (time.time() - start) * 1000.0

            return {
                "ok": False,
                "error": str(exc),
                "latency_ms": round(latency_ms, 2),
            }

    return _redis_check


def _register_dependency_checks() -> None:
    register_healthcheck("database", _make_db_check())
    register_healthcheck("redis", _make_redis_check())


def _make_migrations_check() -> HealthCheckFn:
    def _migrations_check() -> HealthCheckResult:
        try:
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names() or [])

            if "alembic_version" not in tables and "version" not in tables:
                return {
                    "ok": False,
                    "error": "no_migration_table",
                    "latency_ms": 0.0,
                }

            try:
                row = db.session.execute(
                    text(
                        "SELECT version_num "
                        "FROM alembic_version "
                        "LIMIT 1"
                    )
                ).first()

                applied = bool(row and row[0])

                return {
                    "ok": applied,
                    "version": row[0] if row else None,
                    "latency_ms": 0.0,
                }

            except Exception as exc:
                _logger.debug(
                    "Migrations check query failed: %s",
                    exc,
                    exc_info=True,
                )

                return {
                    "ok": False,
                    "error": str(exc),
                    "latency_ms": 0.0,
                }

        except Exception as exc:
            _logger.debug(
                "Migrations check failed: %s",
                exc,
                exc_info=True,
            )

            return {
                "ok": False,
                "error": str(exc),
                "latency_ms": 0.0,
            }

    return _migrations_check


# =============================================================================
# Structured logging with Correlation IDs
# =============================================================================
class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            cid = getattr(g, "correlation_id", None)
        except Exception:
            cid = None

        if not cid:
            try:
                hdr = request.headers
                cid = hdr.get("X-Correlation-ID") or hdr.get("X-Request-ID")
            except Exception:
                cid = None

        if not cid:
            cid_hex = uuid.uuid4().hex[:8]
            cid = getattr(record, "correlation_id", None) or f"cid-{cid_hex}"

        record.correlation_id = cid
        return True


def setup_logging(app: Flask) -> None:
    """
    Centralized logging configuration that prevents duplicate log emissions
    and standardizes PID formatting across handlers.
    """
    loggers = [
        logging.getLogger("PlaidBridgeOpenBankingApi"),
        app.logger if app else None,
    ]

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s [PID: %(process)d]"
    )

    for logger in filter(None, loggers):
        logger.propagate = False
        logger.setLevel(logging.INFO)

        if logger.hasHandlers():
            logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def _setup_logging(flask_app: Flask) -> None:
    """Internal factory logger setup using correlation filtering on stdout."""
    setup_logging(flask_app)
    cid_filter = CorrelationIdFilter()

    for h in flask_app.logger.handlers:
        h.addFilter(cid_filter)


# =============================================================================
# Diagnostics + dependency graph
# =============================================================================
def _gather_diagnostics(flask_app: Flask) -> Dict[str, Any]:
    try:
        diag_mod = importlib.import_module("app.diagnostics")
        return diag_mod.gather_diagnostics(flask_app)
    except Exception:
        return {
            "app": flask_app.import_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": "minimal diagnostics fallback",
        }


def _build_dependency_graph(flask_app: Flask) -> Dict[str, Any]:
    try:
        diag_mod = importlib.import_module("app.diagnostics")
        return diag_mod.build_dependency_graph(flask_app)
    except Exception:
        return {"nodes": [], "edges": [], "dot": "digraph {}"}


def _register_core_routes(flask_app: Flask) -> None:
    """
    Register core diagnostics routes including /healthz, /readyz, /version,
    /diagnostics, /dependency_graph, and /metrics.
    Safe to call unconditionally from create_app().
    """
    try:
        dependency_graph_data = _build_dependency_graph(flask_app)
    except Exception as exc:
        _logger.debug("Failed to build dependency graph", exc_info=exc)
        dependency_graph_data = {"nodes": [], "edges": [], "dot": "digraph {}"}

    try:
        def _run_readiness_checks() -> Tuple[Response, int]:
            results = _registry.run_all()
            overall_ok = all(v.get("ok", False) for v in results.values())

            try:
                start_time = float(
                    flask_app.config.get("APP_START_TIME", time.time())
                )
                uptime = max(0.0, time.time() - start_time)
            except (TypeError, ValueError):
                uptime = 0.0

            payload: Dict[str, Any] = {
                "healthy": overall_ok,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime": uptime,
                "checks": results,
            }

            return jsonify(payload), 200 if overall_ok else 503

        if "readyz" not in flask_app.view_functions:

            @flask_app.route("/readyz", methods=["GET"])
            def readyz() -> Tuple[Response, int]:
                return _run_readiness_checks()

        if "healthz" not in flask_app.view_functions:

            @flask_app.route("/healthz", methods=["GET"])
            def healthz() -> Tuple[Response, int]:
                return _run_readiness_checks()

        if "version" not in flask_app.view_functions:

            @flask_app.route("/version", methods=["GET"])
            def version() -> Tuple[Response, int]:
                pkg_version = flask_app.config.get("APP_VERSION", "unknown")
                git_sha = flask_app.config.get("GIT_SHA")
                payload: Dict[str, Any] = {
                    "version": pkg_version,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                if git_sha:
                    payload["git_sha"] = git_sha
                return jsonify(payload), 200

        if "diagnostics" not in flask_app.view_functions:

            @flask_app.route("/diagnostics", methods=["GET"])
            def diagnostics() -> Tuple[Response, int]:
                return jsonify(_gather_diagnostics(flask_app)), 200

        if "dependency_graph" not in flask_app.view_functions:

            @flask_app.route("/dependency_graph", methods=["GET"])
            def dependency_graph() -> Tuple[Response, int]:
                return jsonify(dependency_graph_data), 200

        if "metrics" not in flask_app.view_functions:

            @flask_app.route("/metrics", methods=["GET"])
            def metrics() -> Tuple[Response, int]:
                try:
                    start_t = float(
                        flask_app.config.get("APP_START_TIME", time.time())
                    )
                    uptime_seconds = max(0.0, time.time() - start_t)
                except Exception:
                    uptime_seconds = 0.0
                payload = {
                    "uptime_seconds": uptime_seconds,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return jsonify(payload), 200

    except Exception:
        _logger.debug(
            "_register_core_routes failed",
            exc_info=True,
        )


# =============================================================================
# ROUTE HYGIENE: required helpers
# =============================================================================
def _rebuild_rules_by_endpoint(flask_app: Flask) -> None:
    """
    Fully rebuild both url_map._rules and url_map._rules_by_endpoint
    from the current iter_rules() output.
    This is authoritative and should be
    called after route hygiene passes and alias adjustments.
    """
    try:
        rules = list(flask_app.url_map.iter_rules())
        rbep: Dict[str, List[Any]] = {}
        for rule in rules:
            ep = getattr(rule, "endpoint", None)
            if ep:
                rbep.setdefault(ep, []).append(rule)

        _replace_url_map_rules(flask_app, rules, rbep)

    except Exception:
        flask_app.logger.debug(
            "_rebuild_rules_by_endpoint failed", exc_info=True
        )


def _prune_ignorable_route_rules(app: Flask) -> None:
    """
    Prune temporary, legacy, or internal routes not present on the whitelist.
    Handles removal defensive guards across both _rules and
    _rules_by_endpoint.
    """
    try:
        if not hasattr(app, "url_map"):
            return

        for rule in list(app.url_map.iter_rules()):
            endpoint = getattr(rule, "endpoint", "")
            path = getattr(rule, "rule", "")

            if endpoint in ROUTE_PRUNE_WHITELIST:
                continue

            should_prune = (
                endpoint.startswith("tmp_")
                or endpoint.startswith("legacy_")
                or endpoint.endswith("__temp")
                or "/_tmp/" in path
            )

            if not should_prune:
                continue

            try:
                rules_list = getattr(app.url_map, "_rules", None)
                if rules_list and rule in rules_list:
                    rules_list.remove(rule)
            except Exception:
                app.logger.debug(
                    "Failed to remove ignorable rule %r",
                    rule,
                    exc_info=True,
                )

            try:
                rbep: Dict[str, List[Any]] = getattr(
                    app.url_map, "_rules_by_endpoint", {}
                )
                endpoint_rules = rbep.get(endpoint, [])
                if rule in endpoint_rules:
                    endpoint_rules.remove(rule)
            except Exception:
                app.logger.debug(
                    "Failed to remove endpoint rule %r for %s",
                    rule,
                    endpoint,
                    exc_info=True,
                )

            app.view_functions.pop(endpoint, None)

    except Exception:
        _logger.debug(
            "_prune_ignorable_route_rules failed",
            exc_info=True,
        )


def _cleanup_premature_oauth_registrations(app: Flask) -> None:
    try:
        oauth_blueprint = app.blueprints.get("oauth")
        if isinstance(oauth_blueprint, Blueprint):
            return

        view_functions = app.view_functions
        premature_endpoints: set[str] = set()

        def is_premature_oauth_view(view: Any) -> bool:
            module_name = getattr(view, "__module__", "")
            return (
                module_name == "app.blueprints.oauth_routes"
                or module_name.startswith("app.blueprints.oauth_routes.")
            )

        # First remove OAuth rules and their associated view functions.
        for rule in list(app.url_map.iter_rules()):
            endpoint = getattr(rule, "endpoint", None)
            if not endpoint:
                continue

            view = view_functions.get(endpoint)
            if view is None or not is_premature_oauth_view(view):
                continue

            premature_endpoints.add(endpoint)

            try:
                app.url_map._rules.remove(rule)
            except ValueError:
                _logger.debug(
                    "Rule %r was not present in app.url_map._rules",
                    rule,
                    exc_info=True,
                )
            except Exception:
                _logger.debug(
                    "Failed to remove rule %r for endpoint %s",
                    rule,
                    endpoint,
                    exc_info=True,
                )

            try:
                rules_by_endpoint = getattr(
                    app.url_map,
                    "_rules_by_endpoint",
                    {},
                )
                rules_for_endpoint = rules_by_endpoint.get(endpoint, [])

                if rule in rules_for_endpoint:
                    rules_for_endpoint.remove(rule)
            except Exception:
                _logger.debug(
                    "Failed to update rules_by_endpoint for endpoint %s",
                    endpoint,
                    exc_info=True,
                )

            view_functions.pop(endpoint, None)

        # Also remove orphaned OAuth views that have no URL rule.
        registered_endpoints = {
            getattr(rule, "endpoint", None)
            for rule in app.url_map.iter_rules()
        }

        for endpoint, view in list(view_functions.items()):
            if (
                endpoint
                and endpoint.startswith("oauth.")
                and endpoint not in registered_endpoints
                and is_premature_oauth_view(view)
            ):
                premature_endpoints.add(endpoint)
                view_functions.pop(endpoint, None)

        if premature_endpoints:
            _logger.info(
                "Removed premature oauth endpoints: %s",
                ", ".join(sorted(premature_endpoints)),
            )

    except Exception:
        _logger.debug(
            "_cleanup_premature_oauth_registrations failed",
            exc_info=True,
        )


def _reconcile_oauth_callback_aliases(app: Flask) -> None:
    try:
        rules = list(app.url_map.iter_rules())

        for rule in rules:
            endpoint = getattr(rule, "endpoint", "")
            if endpoint.endswith("_alias"):
                app.view_functions.pop(endpoint, None)

                try:
                    app.url_map._rules.remove(rule)
                except Exception:
                    app.logger.debug(
                        "Failed to remove alias rule %r",
                        rule,
                        exc_info=True,
                    )

                try:
                    rbep: Dict[str, List[Any]] = getattr(
                        app.url_map, "_rules_by_endpoint", {}
                    )
                    ep_rules = rbep.get(endpoint, [])
                    if rule in ep_rules:
                        ep_rules.remove(rule)
                except Exception:
                    app.logger.debug(
                        "Failed to remove alias endpoint rule %r",
                        rule,
                        endpoint,
                        exc_info=True,
                    )

    except Exception:
        _logger.debug(
            "_reconcile_oauth_callback_aliases failed", exc_info=True
        )


def _enforce_route_uniqueness(flask_app: Flask) -> None:
    """Ensure endpoints are unique and that url_map._rules_by_endpoint is consistent."""
    try:
        if not hasattr(flask_app, "url_map"):
            return

        seen: Dict[Tuple[str, Tuple[str, ...]], Any] = {}
        duplicates: List[Any] = []

        for rule in list(flask_app.url_map.iter_rules()):
            path = getattr(rule, "rule", "") or ""
            methods = tuple(
                sorted(
                    [
                        m
                        for m in getattr(rule, "methods", set())
                        if m not in ("HEAD", "OPTIONS")
                    ]
                )
            )
            key = (path, methods)
            if key in seen:
                duplicates.append(rule)
            else:
                seen[key] = rule

        if not duplicates:
            return

        for rule in duplicates:
            try:
                lst = getattr(flask_app.url_map, "_rules", None)
                if lst and rule in lst:
                    lst.remove(rule)
            except Exception:
                pass
    except Exception:
        _logger.debug("_enforce_route_uniqueness failed", exc_info=True)


def _dedupe_rules(flask_app: Flask) -> None:
    """Remove duplicate (path, methods, endpoint) rules while preserving the first occurrence."""
    try:
        if not hasattr(flask_app, "url_map"):
            return

        seen: Set[Tuple[str, Tuple[str, ...], Optional[str]]] = set()
        to_remove: List[Any] = []

        for rule in list(flask_app.url_map.iter_rules()):
            path = getattr(rule, "rule", "") or ""
            methods = tuple(
                sorted(
                    [
                        m
                        for m in getattr(rule, "methods", set())
                        if m not in ("HEAD", "OPTIONS")
                    ]
                )
            )
            endpoint = getattr(rule, "endpoint", None)
            key = (path, methods, endpoint)
            if key in seen:
                to_remove.append(rule)
            else:
                seen.add(key)

        for rule in to_remove:
            try:
                lst = getattr(flask_app.url_map, "_rules", None)
                if lst and rule in lst:
                    lst.remove(rule)
            except Exception:
                pass
    except Exception:
        _logger.debug("_dedupe_rules failed", exc_info=True)


def _stabilize_rules_order(flask_app: Flask) -> None:
    """Stabilize rule ordering deterministically to reduce flakiness in tests."""
    try:
        if not hasattr(flask_app, "url_map"):
            return

        try:
            rules = list(flask_app.url_map.iter_rules())
            rules_sorted = sorted(
                rules,
                key=lambda r: (
                    getattr(r, "rule", ""),
                    getattr(r, "endpoint", ""),
                ),
            )
            rbep: Dict[str, List[Any]] = getattr(
                flask_app.url_map, "_rules_by_endpoint", {}
            )
            _replace_url_map_rules(flask_app, rules_sorted, rbep)
        except Exception:
            pass
    except Exception:
        _logger.debug("_stabilize_rules_order failed", exc_info=True)


# =============================================================================
# Auth Loaders
# =============================================================================
def _register_login_manager_loader(flask_app: Flask) -> None:
    """
    Explicit Proxy Loader for Flask-Login.
    This function registers a proxy `user_loader` at startup to satisfy
    Flask-Login's requirement for a registered loader, but intentionally
    defers the actual module import to runtime.
    This guarantees the authoritative loader in app/auth_handlers.py
    is executed strictly when a session is evaluated, effectively bypassing
    any sys.modules caching interference that could strip the loader during
    the factory boot sequence.
    """
    try:
        lm = (
            getattr(flask_app, "login_manager", None)
            or flask_app.extensions.get("login_manager")
            or flask_app.extensions.get("flask_login")
            or globals().get("login_manager")
        )
        if not lm:
            flask_app.logger.debug(
                "Flask-Login LoginManager instance not found; "
                "skipping proxy loader registration."
            )
            return

        @lm.user_loader
        def proxy_load_user(user_id: str) -> Any:
            try:
                from app.auth_handlers import load_user

                return load_user(user_id)
            except Exception as e:
                flask_app.logger.error(
                    f"Runtime proxy_load_user failed for ID {user_id}: {e}",
                    exc_info=True,
                )
                return None

    except Exception:
        flask_app.logger.debug(
            "_register_login_manager_loader failed", exc_info=True
        )


def _register_jwt_loaders(flask_app: Flask) -> None:
    """
    Registers robust JWT identity, lookup, and blocklist loaders optimized
    for UUID strings, preserving legacy integer paths and the SystemOperator GOD-MODE
    intercept.
    """
    extensions = getattr(flask_app, "extensions", {})
    jwt_manager = (
        extensions.get("jwt")
        or extensions.get("flask_jwt_extended")
        or extensions.get("flask-jwt-extended")
        or globals().get("jwt")
    )
    if not jwt_manager:
        return

    @jwt_manager.user_identity_loader
    def user_identity_lookup(user: Any) -> str:
        if isinstance(user, str):
            return user
        if hasattr(user, "id"):
            return str(user.id)
        return str(user)

    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header: dict, jwt_data: dict) -> Any:
        identity = jwt_data.get("sub")
        if not identity:
            return None
        from app.auth_handlers import _resolve_identity

        return _resolve_identity(identity)

    @jwt_manager.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header: dict, jwt_data: dict) -> bool:
        try:
            from app.auth_handlers import is_token_revoked

            return is_token_revoked(_jwt_header, jwt_data)
        except Exception:
            return False


# =============================================================================
# Alias Fallbacks Refactor Helper
# =============================================================================
def _apply_alias_fallbacks(app: Flask, old_prefix: str, new_prefix: str) -> None:
    """
    Registers legacy alias endpoints in both `view_functions` and `url_map`
    so that `url_for()` calls targeting legacy blueprints (e.g., `admin_ui.*`)
    resolve without throwing Werkzeug BuildError exceptions.
    """
    for rule in list(app.url_map.iter_rules()):
        if rule.endpoint.startswith(old_prefix):
            new_endpoint = rule.endpoint.replace(old_prefix, new_prefix, 1)
            view_func = app.view_functions.get(rule.endpoint)

            if view_func and new_endpoint not in app.view_functions:
                app.view_functions[new_endpoint] = view_func

            # Verify if rule/method combination already exists under new_endpoint
            existing_endpoints = {
                r.endpoint
                for r in app.url_map.iter_rules()
                if r.rule == rule.rule and set(r.methods or []) == set(rule.methods or [])
            }

            if new_endpoint not in existing_endpoints:
                app.add_url_rule(
                    rule.rule,
                    endpoint=new_endpoint,
                    view_func=view_func,
                    methods=rule.methods,
                    defaults=rule.defaults,
                    subdomain=rule.subdomain,
                    strict_slashes=rule.strict_slashes,
                )


# =============================================================================
# Application Factory
# =============================================================================
def create_app(
    config_class: Any = None,
    env_name: Optional[str] = None,
    **kwargs: Any,
) -> Flask:
    """
    Unified Flask application factory.

    Supports:
        create_app()
        create_app("testing")
        create_app(env_name="testing")
        create_app(config_class=TestingConfig)
        create_app(config_class="app.config.TestingConfig")
    """
    app = Flask(__name__)

    # Normalize positional environment names passed as config_class
    if (
        isinstance(config_class, str)
        and config_class.lower() in CONFIG_MAP
        and env_name is None
    ):
        env_name = config_class
        config_class = None

    # Resolve target environment key
    requested_env = (
        env_name
        or os.getenv("ENV_NAME")
        or os.getenv("FLASK_ENV")
        or "production"
    ).lower()

    # Select configuration class if explicit override wasn't provided
    if config_class is None:
        config_class = get_config_class(requested_env)

    # Load configuration object into application context
    try:
        app.config.from_object(config_class)

    except Exception as cfg_err:
        _logger.warning(
            "Failed to load config class '%s': %s",
            config_class,
            cfg_err,
        )

        # Preserve testing behavior if configuration loading fails
        if requested_env == "testing":
            app.config["TESTING"] = True
            app.config.setdefault(
                "SQLALCHEMY_DATABASE_URI",
                "sqlite:///:memory:",
            )

        # Fall back to default config class
        default_cfg = get_config_class()

        if default_cfg is not config_class:
            try:
                app.config.from_object(default_cfg)
            except Exception as fallback_err:
                _logger.warning(
                    "Failed to load fallback config class '%s': %s",
                    default_cfg,
                    fallback_err,
                )

        if requested_env == "testing":
            app.config["TESTING"] = True
            app.config.setdefault(
                "SQLALCHEMY_DATABASE_URI",
                "sqlite:///:memory:",
            )

    # Apply keyword argument configuration overrides
    for key, value in kwargs.items():
        app.config[key] = value

    _setup_logging(app)

    # Log loaded configuration class name for auditing and test assertions
    cfg_name = getattr(config_class, "__name__", str(config_class))
    app.logger.info("Loaded configuration class: %s", cfg_name)

    # Register dependency health checks
    _register_dependency_checks()

    # Initialize extensions (socketio, db, etc.)
    init_extensions(app)
    _ = socketio  # Reference extension to confirm module binding

    # Register blueprints & CLI commands
    _register_blueprints(app)
    app.register_blueprint(treasury_bp, url_prefix="/api/v1/treasury")
    app.register_blueprint(webhooks, url_prefix="/webhooks")

    # Standardized Blueprint Binding Diagnostics
    for var_name, bp in app.blueprints.items():
        app.logger.info(
            "🔗 Operational blueprint link bound: variable=%s name=%s -> %s (Prefix mapping: %s)",
            var_name,
            bp.name,
            bp.import_name,
            bp.url_prefix or "ROOT",
        )

    register_cli_commands(app)
    _register_cli_commands(app)
    ensure_admin_aliases(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register auth loaders
    _register_login_manager_loader(app)
    _register_jwt_loaders(app)

    # Ensure DB tables
    _ensure_db_tables(app)

    # Register core diagnostic routes
    _register_core_routes(app)

    # Route hygiene and alias fallbacks
    _ensure_admin_index_registered(app)
    _prune_ignorable_route_rules(app)
    _cleanup_premature_oauth_registrations(app)
    _reconcile_oauth_callback_aliases(app)

    # Apply alias fallbacks with refactored deduplication and url_map sync logic
    _apply_alias_fallbacks(app, "admin_bp.", "admin_ui.")
    _apply_alias_fallbacks(app, "admin.", "admin_ui.")
    _apply_alias_fallbacks(app, "main_bp.", "main.")

    _enforce_route_uniqueness(app)
    _dedupe_rules(app)
    _stabilize_rules_order(app)
    _rebuild_rules_by_endpoint(app)

    return app


# Application aliases and backward-compatibility shims
get_app = create_app
legacy_get_app = create_app

# =============================================================================
# Direct Execution Entrypoint
# =============================================================================
if __name__ == "__main__":
    app = create_app()
    app.run()