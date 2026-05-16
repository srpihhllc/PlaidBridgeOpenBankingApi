# =============================================================================
# FILE: app/__init__.py
# DESCRIPTION: Unified, hardened, cockpit-grade Flask application factory.
#              Single authoritative blueprint registration path, single
#              authoritative url_map rebuild, defensive guards to avoid
#              double-registration and preserve admin UI aliases.
# =============================================================================

from __future__ import annotations

import importlib
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import Flask, jsonify, request, g, Response, current_app
from sqlalchemy import inspect, text
from werkzeug.exceptions import BadRequest, HTTPException

from app.blueprints import register_blueprints, validate_blueprints_graph
from .config import get_config_class
from .extensions import db, init_extensions, jwt, login_manager, socketio

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration: conservative defaults and test-friendly hooks
# ---------------------------------------------------------------------------
DEFAULT_ALLOW_PREMATURE_CLEANUP = True

ROUTE_PRUNE_WHITELIST: List[str] = [
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
]

_maybe_redis_client = None

# =============================================================================
# Internal helpers
# =============================================================================


def _safe_status_code(code: Any) -> int:
    try:
        return int(code)
    except Exception:
        return 500


def _register_blueprints(flask_app: Flask) -> None:
    """
    Auto-discovery blueprint loader with duplicate registration guards.
    Temporarily wraps Flask.register_blueprint to skip already-registered
    blueprint names. Restores original method immediately after.
    """
    try:
        _original_register_blueprint = flask_app.register_blueprint

        def _guarded_register_blueprint(bp, **options):
            bp_name = getattr(bp, "name", None)
            if bp_name and bp_name in flask_app.blueprints:
                flask_app.logger.debug(
                    "Auto-discovery: blueprint '%s' already registered; skipping.", bp_name
                )
                return
            return _original_register_blueprint(bp, **options)

        flask_app.register_blueprint = _guarded_register_blueprint  # type: ignore[method-assign]
        try:
            register_blueprints(flask_app)
            validate_blueprints_graph(flask_app)
        finally:
            flask_app.register_blueprint = _original_register_blueprint  # type: ignore[method-assign]

    except Exception as exc:
        flask_app.logger.error("❌ Blueprint auto-registration failed: %s", exc, exc_info=True)
        raise


# =============================================================================
# Error handlers
# =============================================================================
def _register_error_handlers(flask_app: Flask) -> None:
    def _handle_exception(e: Exception):
        if isinstance(e, HTTPException):
            status = _safe_status_code(getattr(e, "code", 500))
            description = getattr(e, "description", str(e))
            name = getattr(e, "name", "HTTPException")
        else:
            status = 500
            description = str(e)
            name = type(e).__name__

        if status == 400 and isinstance(e, BadRequest):
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
            "HTTP %s (%s): %s", status, name, description
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
        if not fn:
            return {"ok": False, "error": "not_registered", "latency_ms": 0.0}

        try:
            res = fn()
            if not isinstance(res, dict):
                return {"ok": False, "error": "invalid_result_type", "latency_ms": 0.0}
            res["ok"] = bool(res.get("ok", False))
            res.setdefault("latency_ms", 0.0)
            return res
        except Exception as exc:
            _logger.debug("Health check '%s' raised: %s", name, exc, exc_info=True)
            return {"ok": False, "error": str(exc), "latency_ms": 0.0}

    def run_all(self) -> Dict[str, HealthCheckResult]:
        return {name: self.run_check(name) for name in sorted(self._checks.keys())}

    def list_checks(self) -> Tuple[str, ...]:
        return tuple(sorted(self._checks.keys()))


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
            return {"ok": True, "latency_ms": round(latency_ms, 2)}
        except Exception as exc:
            latency_ms = (time.time() - start) * 1000.0
            return {"ok": False, "error": str(exc), "latency_ms": round(latency_ms, 2)}
    return _db_check


def _make_redis_check() -> HealthCheckFn:
    def _redis_check() -> HealthCheckResult:
        start = time.time()
        try:
            rc = getattr(current_app, "redis_client", None) or _maybe_redis_client
            if not rc:
                return {"ok": False, "error": "no_client", "latency_ms": 0.0}
            pong = rc.ping() if hasattr(rc, "ping") else True
            latency_ms = (time.time() - start) * 1000.0
            return {"ok": bool(pong), "latency_ms": round(latency_ms, 2)}
        except Exception as exc:
            latency_ms = (time.time() - start) * 1000.0
            return {"ok": False, "error": str(exc), "latency_ms": round(latency_ms, 2)}
    return _redis_check


def _make_migrations_check() -> HealthCheckFn:
    def _migrations_check() -> HealthCheckResult:
        try:
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names() or [])

            if "alembic_version" not in tables and "version" not in tables:
                return {"ok": False, "error": "no_migration_table", "latency_ms": 0.0}

            try:
                row = db.session.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).first()
                applied = bool(row and row[0])
                return {"ok": applied, "version": (row[0] if row else None), "latency_ms": 0.0}
            except Exception as exc:
                _logger.debug("Migrations check query failed: %s", exc, exc_info=True)
                return {"ok": False, "error": str(exc), "latency_ms": 0.0}

        except Exception as exc:
            _logger.debug("Migrations check failed: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc), "latency_ms": 0.0}
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
                cid = (
                    request.headers.get("X-Correlation-ID")
                    or request.headers.get("X-Request-ID")
                )
            except Exception:
                cid = None

        if not cid:
            cid = getattr(record, "correlation_id", None) or f"cid-{uuid.uuid4().hex[:8]}"

        record.correlation_id = cid
        return True


def _setup_logging(flask_app: Flask) -> None:
    flask_app.logger.setLevel(logging.INFO)
    cid_filter = CorrelationIdFilter()

    if not flask_app.logger.handlers:
        handler = logging.StreamHandler()
        fmt = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"correlation_id":"%(correlation_id)s","module":"%(module)s",'
            '"message":"%(message)s"}'
        )
        handler.setFormatter(logging.Formatter(fmt))
        handler.addFilter(cid_filter)
        flask_app.logger.addHandler(handler)
    else:
        for h in flask_app.logger.handlers:
            h.addFilter(cid_filter)


# =============================================================================
# Diagnostics + dependency graph
# =============================================================================
def _gather_diagnostics(flask_app: Flask) -> Dict[str, Any]:
    try:
        from .diagnostics import gather_diagnostics
        return gather_diagnostics(flask_app)
    except Exception:
        return {
            "app": flask_app.import_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "notes": "minimal diagnostics fallback",
        }


def _build_dependency_graph(flask_app: Flask) -> Dict[str, Any]:
    try:
        from .diagnostics import build_dependency_graph
        return build_dependency_graph(flask_app)
    except Exception:
        return {"nodes": [], "edges": [], "dot": "digraph {}"}


def _register_core_routes(flask_app: Flask) -> None:
    """
    Register core diagnostics routes other than /health and /healthz.
    Safe to call unconditionally from create_app().
    """
    try:
        # readyz
        if "readyz" not in flask_app.view_functions:
            @flask_app.route("/readyz", methods=["GET"])
            def readyz() -> Response:
                results = _registry.run_all()
                overall_ok = all(v.get("ok", False) for v in results.values())
                return jsonify({"ok": overall_ok, "checks": results}), 200 if overall_ok else 503

        # version
        if "version" not in flask_app.view_functions:
            @flask_app.route("/version", methods=["GET"])
            def version() -> Response:
                pkg_version = flask_app.config.get("APP_VERSION", "unknown")
                git_sha = flask_app.config.get("GIT_SHA")
                payload: Dict[str, Any] = {
                    "version": pkg_version,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                if git_sha:
                    payload["git_sha"] = git_sha
                return jsonify(payload), 200

        # diagnostics
        if "diagnostics" not in flask_app.view_functions:
            @flask_app.route("/diagnostics", methods=["GET"])
            def diagnostics() -> Response:
                return jsonify(_gather_diagnostics(flask_app)), 200

        # dependency_graph
        if "dependency_graph" not in flask_app.view_functions:
            @flask_app.route("/dependency_graph", methods=["GET"])
            def dependency_graph() -> Response:
                return jsonify(_build_dependency_graph(flask_app)), 200

        # metrics
        if "metrics" not in flask_app.view_functions:
            @flask_app.route("/metrics", methods=["GET"])
            def metrics() -> Response:
                try:
                    uptime_seconds = max(
                        0.0,
                        time.time() - float(flask_app.config.get("APP_START_TIME", time.time())),
                    )
                except Exception:
                    uptime_seconds = 0.0
                payload = {
                    "uptime_seconds": uptime_seconds,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                return jsonify(payload), 200

    except Exception:
        flask_app.logger.debug("_register_core_routes failed", exc_info=True)


# =============================================================================
# ROUTE HYGIENE: required helper (the missing piece)
# =============================================================================
def _rebuild_rules_by_endpoint(flask_app: Flask) -> None:
    """
    Fully rebuild both url_map._rules and url_map._rules_by_endpoint
    from the current iter_rules() output. This is authoritative and should be
    called once at the end of create_app() after all registration and hygiene.
    """
    try:
        rules = list(flask_app.url_map.iter_rules())

        # Rebuild _rules (canonical ordering)
        setattr(flask_app.url_map, "_rules", rules)

        # Rebuild _rules_by_endpoint
        rbep = {}
        for rule in rules:
            ep = getattr(rule, "endpoint", None)
            if ep:
                rbep.setdefault(ep, []).append(rule)

        setattr(flask_app.url_map, "_rules_by_endpoint", rbep)

    except Exception:
        flask_app.logger.debug("_rebuild_rules_by_endpoint failed", exc_info=True)


# =============================================================================
# Legacy compatibility helpers required by test_route_cleanup.py
# =============================================================================
def _cleanup_premature_oauth_registrations(flask_app: Flask) -> None:
    """
    Remove prematurely-registered oauth.* endpoints whose blueprint hasn't been
    registered yet. Non-destructive: do not call _rebuild_rules_by_endpoint here.
    Caller will perform a single final rebuild.
    """
    try:
        if not hasattr(flask_app, "view_functions") or not hasattr(flask_app, "url_map"):
            return

        removed: List[str] = []

        for endpoint, view_func in list(flask_app.view_functions.items()):
            if endpoint == "static":
                continue

            mod = getattr(view_func, "__module__", "") or ""
            if not mod.startswith("app.blueprints.oauth_routes"):
                continue

            blueprint_name = endpoint.split(".", 1)[0] if "." in endpoint else None
            if blueprint_name and blueprint_name in flask_app.blueprints:
                continue

            flask_app.view_functions.pop(endpoint, None)

            rules_to_remove = [
                r for r in list(flask_app.url_map.iter_rules())
                if getattr(r, "endpoint", None) == endpoint
            ]
            for rule in rules_to_remove:
                try:
                    try:
                        lst = getattr(flask_app.url_map, "_rules", None)
                        if lst and rule in lst:
                            lst.remove(rule)
                    except Exception:
                        pass

                    try:
                        rbep = getattr(flask_app.url_map, "_rules_by_endpoint", {}) or {}
                        lst_ep = rbep.get(endpoint)
                        if lst_ep:
                            try:
                                lst_ep.remove(rule)
                            except ValueError:
                                pass
                            if not lst_ep:
                                rbep.pop(endpoint, None)
                                try:
                                    setattr(flask_app.url_map, "_rules_by_endpoint", rbep)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                except Exception:
                    _logger.debug(
                        "Failed to remove rule %r for endpoint %s", rule, endpoint, exc_info=True
                    )

            removed.append(endpoint)

        if removed:
            try:
                flask_app.logger.info("Removed premature oauth endpoints: %s", ", ".join(removed))
            except Exception:
                pass

            # Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    except Exception:
        _logger.debug("_cleanup_premature_oauth_registrations failed", exc_info=True)


def add_route_prune_whitelist(endpoint: str) -> List[str]:
    """
    Add an endpoint to the ROUTE_PRUNE_WHITELIST.
    Tests expect this to exist and mutate the global whitelist.
    """
    if endpoint and endpoint not in ROUTE_PRUNE_WHITELIST:
        ROUTE_PRUNE_WHITELIST.append(endpoint)
    return ROUTE_PRUNE_WHITELIST


# =============================================================================
# Route hygiene helpers (non-destructive during registration)
# =============================================================================
def _prune_ignorable_route_rules(flask_app: Flask) -> None:
    """
    Remove rules that are clearly ignorable (temporary, legacy, or in whitelist).
    Conservative: do not call _rebuild_rules_by_endpoint here; caller will rebuild once.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return

        to_remove: List[Tuple[str, Any]] = []
        for rule in list(flask_app.url_map.iter_rules()):
            ep = getattr(rule, "endpoint", None)
            if not ep:
                continue
            if ep in ROUTE_PRUNE_WHITELIST:
                continue
            name = str(ep)
            path = getattr(rule, "rule", "") or ""
            if (
                name.startswith("tmp_")
                or name.startswith("legacy_")
                or "__temp" in name
                or "/_tmp/" in path
            ):
                to_remove.append((ep, rule))

        if not to_remove:
            return

        for ep, rule in to_remove:
            try:
                lst = getattr(flask_app.url_map, "_rules", None)
                if lst and rule in lst:
                    lst.remove(rule)
            except Exception:
                pass
            try:
                rbep = getattr(flask_app.url_map, "_rules_by_endpoint", {}) or {}
                rbep = {k: [r for r in v if r is not rule] for k, v in rbep.items()}
                try:
                    setattr(flask_app.url_map, "_rules_by_endpoint", rbep)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                flask_app.view_functions.pop(ep, None)
            except Exception:
                pass

        # Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    except Exception:
        _logger.debug("_prune_ignorable_route_rules failed", exc_info=True)


def _reconcile_oauth_callback_aliases(flask_app: Flask) -> None:
    """
    Ensure oauth callback endpoints are canonical and remove alias duplicates.
    Non-destructive: remove view_functions and rules but do not rebuild internals here.
    """
    try:
        if not hasattr(flask_app, "view_functions"):
            return

        alias_map = {
            "oauth.callback_google_alias": "oauth.callback_google",
        }

        for alias, canonical in alias_map.items():
            if alias in flask_app.view_functions and canonical in flask_app.view_functions:
                flask_app.view_functions.pop(alias, None)
                rules_to_remove = [
                    r for r in list(flask_app.url_map.iter_rules())
                    if getattr(r, "endpoint", None) == alias
                ]
                for rule in rules_to_remove:
                    try:
                        lst = getattr(flask_app.url_map, "_rules", None)
                        if lst and rule in lst:
                            lst.remove(rule)
                    except Exception:
                        pass
                    try:
                        rbep = getattr(flask_app.url_map, "_rules_by_endpoint", {}) or {}
                        lst_ep = rbep.get(alias)
                        if lst_ep:
                            try:
                                lst_ep.remove(rule)
                            except Exception:
                                pass
                            if not lst_ep:
                                rbep.pop(alias, None)
                                try:
                                    setattr(flask_app.url_map, "_rules_by_endpoint", rbep)
                                except Exception:
                                    pass
                    except Exception:
                        pass

        # Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    except Exception:
        _logger.debug("_reconcile_oauth_callback_aliases failed", exc_info=True)


def _enforce_route_uniqueness(flask_app: Flask) -> None:
    """
    Ensure endpoints are unique and that url_map._rules_by_endpoint is consistent.
    Remove duplicates by (path, methods) pairs. Do not rebuild internals here.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return

        seen: Dict[Tuple[str, Tuple[str, ...]], Any] = {}
        duplicates: List[Any] = []

        for rule in list(flask_app.url_map.iter_rules()):
            path = getattr(rule, "rule", "") or ""
            methods = tuple(
                sorted(
                    [m for m in getattr(rule, "methods", set()) if m not in ("HEAD", "OPTIONS")]
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

        # Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    except Exception:
        _logger.debug("_enforce_route_uniqueness failed", exc_info=True)


def _dedupe_rules(flask_app: Flask) -> None:
    """
    Remove duplicate (path, methods, endpoint) rules while preserving the first
    occurrence. Conservative: only removes exact duplicates. Do not rebuild here.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return

        seen = set()
        to_remove: List[Any] = []

        for rule in list(flask_app.url_map.iter_rules()):
            path = getattr(rule, "rule", "") or ""
            methods = tuple(
                sorted(
                    [m for m in getattr(rule, "methods", set()) if m not in ("HEAD", "OPTIONS")]
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

        # Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    except Exception:
        _logger.debug("_dedupe_rules failed", exc_info=True)


def _stabilize_rules_order(flask_app: Flask) -> None:
    """
    Stabilize rule ordering deterministically to reduce flakiness in tests.
    Sort by (rule.rule, endpoint) and reassign internal lists.
    Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return

        try:
            rules = list(flask_app.url_map.iter_rules())
            rules_sorted = sorted(
                rules,
                key=lambda r: (getattr(r, "rule", ""), getattr(r, "endpoint", "")),
            )
            setattr(flask_app.url_map, "_rules", rules_sorted)
        except Exception:
            pass

        # Do not rebuild here; caller will call _rebuild_rules_by_endpoint once.
    except Exception:
        _logger.debug("_stabilize_rules_order failed", exc_info=True)


# =============================================================================
# Login manager and JWT loader registration helpers (safe defaults)
# =============================================================================
def _register_login_manager_loader(flask_app: Flask) -> None:
    try:
        if not login_manager:
            return

        @login_manager.user_loader
        def _load_user(user_id: str):
            try:
                from app.models.user import User  # canonical import
                return User.query.get(int(user_id))
            except Exception:
                return None
    except Exception:
        _logger.debug("_register_login_manager_loader failed", exc_info=True)


def _register_jwt_loaders(flask_app: Flask) -> None:
    try:
        if not jwt:
            return

        @jwt.user_identity_loader
        def _jwt_identity(identity):
            return identity

        @jwt.user_lookup_loader
        def _jwt_user_lookup(_jwt_header, jwt_data):
            try:
                from app.models.user import User  # canonical import
                identity = jwt_data.get("sub") or jwt_data.get("identity")
                if identity is None:
                    return None
                return User.query.get(int(identity))
            except Exception:
                return None
    except Exception:
        _logger.debug("_register_jwt_loaders failed", exc_info=True)


# =============================================================================
# BEGIN FINAL UNIFIED create_app() — EXPLICIT-FIRST ORDERING
# =============================================================================
def _ensure_admin_index_registered(flask_app: Flask) -> None:
    """
    Non-destructive check to ensure exactly one /admin endpoint exists.
    This function will NOT add a rule; it only prunes duplicates if present.
    If a view function exists but no rule, it defers to blueprint registration.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return

        umap = flask_app.url_map

        def _is_admin_path(rule):
            return (getattr(rule, "rule", "") or "").rstrip("/") == "/admin"

        existing_admin_rules = [
            r for r in list(umap.iter_rules())
            if getattr(r, "endpoint", None) == "admin.admin_index" and _is_admin_path(r)
        ]

        if existing_admin_rules:
            if len(existing_admin_rules) > 1:
                keep = existing_admin_rules[0]
                duplicates = set(id(r) for r in existing_admin_rules[1:])
                try:
                    if hasattr(umap, "_rules"):
                        umap._rules = [r for r in umap._rules if id(r) not in duplicates]
                except Exception:
                    pass
                try:
                    rbep = getattr(umap, "_rules_by_endpoint", {}) or {}
                    rbep["admin.admin_index"] = [keep]
                    setattr(umap, "_rules_by_endpoint", rbep)
                except Exception:
                    pass
            return

        candidate_vf = flask_app.view_functions.get("admin.admin_index")
        if candidate_vf:
            # Non-destructive: do not add a fallback /admin rule here.
            # If a view function exists but no rule, defer to the canonical
            # blueprint registration to provide the route. Adding a rule here
            # can create duplicates if the blueprint registers later.
            flask_app.logger.debug(
                "Found admin.admin_index view function but no rule; deferring to blueprint registration."
            )
            return
    except Exception:
        flask_app.logger.debug("_ensure_admin_index_registered failed", exc_info=True)


def create_app(
    config_class: Optional[Any] = None,
    env_name: Optional[str] = None,
    config_name: Optional[str] = None,
    **kwargs,
) -> Flask:
    # Pytest passes config_class through **kwargs**, not the named param.
    if config_class is None and "config_class" in kwargs:
        config_class = kwargs.pop("config_class")

    # Resolve dotted-path strings like "app.config.TestConfig"
    if isinstance(config_class, str) and "." in config_class:
        module_name, class_name = config_class.rsplit(".", 1)
        module = importlib.import_module(module_name)
        config_class = getattr(module, class_name)

    # Ensure config_class is a class (not an instance)
    if config_class is not None and not isinstance(config_class, (type, str)):
        config_class = config_class.__class__

    if isinstance(config_class, type):
        original_config_name = config_class.__name__
    else:
        original_config_name = str(config_class)

    if config_class is None:
        original_config_name = os.getenv("FLASK_CONFIG", "default")

    if isinstance(config_class, str):
        config_class = get_config_class(config_class)

    if config_class is None:
        if config_name is None and env_name is not None:
            config_name = env_name
        if config_name is None:
            config_name = os.getenv("FLASK_CONFIG", "default")
        config_class = get_config_class(config_name)

    flask_app = Flask(__name__, instance_relative_config=False)

    try:
        flask_app.config.from_object(config_class)
    except Exception:
        try:
            if isinstance(config_class, str):
                resolved = get_config_class(config_class)
                flask_app.config.from_object(resolved)
                config_class = resolved
            else:
                raise
        except Exception:
            flask_app.logger.exception("Failed to load config_class %r; using defaults", config_class)

    if str(original_config_name).lower().startswith("testing"):
        flask_app.config["TESTING"] = True

    # Install logging early
    _setup_logging(flask_app)
    flask_app.logger.info(f"Using config class: {original_config_name}")

    # Core systems
    _register_error_handlers(flask_app)

    # Initialize extensions
    init_extensions(flask_app)
    _register_login_manager_loader(flask_app)
    _register_jwt_loaders(flask_app)

    # Healthchecks
    register_healthcheck("database", _make_db_check())
    register_healthcheck("migrations", _make_migrations_check())
    register_healthcheck("redis", _make_redis_check())

    flask_app.config["APP_START_TIME"] = time.time()

    # Lightweight /healthz endpoint
    @flask_app.route("/healthz", methods=["GET"])
    def healthz() -> Response:
        results = _registry.run_all()
        overall_ok = all(v.get("ok", False) for v in results.values())

        payload = {
            "healthy": overall_ok,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime": round(
                time.time() - float(flask_app.config.get("APP_START_TIME", time.time())),
                2,
            ),
            "checks": results,
        }
        return jsonify(payload), 200 if overall_ok else 503

    @flask_app.route("/health", methods=["GET"])
    def health_check_simple():
        return {"status": "ok"}, 200

    # ------------------------------------------------------------------
    # ADMIN API blueprints (explicit, guarded)
    # ------------------------------------------------------------------
    try:
        try:
            from .blueprints.admin_routes import admin_api_bp, admin_api_core_bp
        except Exception:
            admin_api_bp = None
            admin_api_core_bp = None
            flask_app.logger.debug(
                "Could not import admin API blueprints; skipping explicit API registration",
                exc_info=True,
            )

        # Explicitly register API-only admin blueprints if not already present.
        # UI admin blueprint is registered via guarded auto-discovery below.
        if admin_api_core_bp and "admin_api_core" not in flask_app.blueprints:
            try:
                flask_app.register_blueprint(admin_api_core_bp)
                flask_app.logger.info("🔗 Registered admin_api_core_bp")
            except Exception:
                flask_app.logger.debug("admin_api_core_bp register skipped", exc_info=True)

        if admin_api_bp and "admin_api" not in flask_app.blueprints:
            try:
                flask_app.register_blueprint(admin_api_bp)
                flask_app.logger.info("🔗 Registered admin_api_bp")
            except Exception:
                flask_app.logger.debug("admin_api_bp register skipped", exc_info=True)
    except Exception:
        flask_app.logger.debug("Admin API explicit registration failed", exc_info=True)

    # ------------------------------------------------------------------
    # AUTO-DISCOVERY BLUEPRINTS (single guarded path)
    # ------------------------------------------------------------------
    try:
        _register_blueprints(flask_app)
    except Exception:
        flask_app.logger.debug("Auto-discovery blueprint registration failed", exc_info=True)

    # ------------------------------------------------------------------
    # OPTIONAL: Register admin UI blueprint (gated by config or test override)
    # ------------------------------------------------------------------
    try:
        admin_ui_enabled = flask_app.config.get("ADMIN_UI_ENABLED", False)
        force_admin_in_tests = flask_app.config.get("FORCE_REGISTER_ADMIN_UI_IN_TESTS", False)
        if admin_ui_enabled or (flask_app.config.get("TESTING") and force_admin_in_tests):
            try:
                from importlib import import_module

                mod = import_module("app.blueprints.admin_ui_routes")
                admin_bp = getattr(mod, "admin_bp", None)
                if admin_bp and "admin" not in flask_app.blueprints:
                    try:
                        flask_app.register_blueprint(admin_bp)
                        flask_app.logger.info("🔗 Registered admin UI blueprint (admin)")
                    except Exception:
                        flask_app.logger.debug("admin blueprint registration skipped", exc_info=True)
            except Exception:
                flask_app.logger.debug("Failed to import/register admin blueprint", exc_info=True)
        else:
            flask_app.logger.debug("ADMIN_UI_ENABLED is False and no test override; skipping admin UI registration.")
    except Exception:
        flask_app.logger.debug("Admin UI registration guard failed", exc_info=True)

    # ------------------------------------------------------------------
    # ROUTE HYGIENE (single canonical pass; non-destructive until final rebuild)
    # ------------------------------------------------------------------
    try:
        _cleanup_premature_oauth_registrations(flask_app)
    except Exception:
        flask_app.logger.debug("Pre-registration oauth cleanup failed", exc_info=True)

    try:
        _prune_ignorable_route_rules(flask_app)
    except Exception:
        flask_app.logger.debug("Prune ignorable route rules failed", exc_info=True)

    try:
        _reconcile_oauth_callback_aliases(flask_app)
    except Exception:
        flask_app.logger.debug("Reconcile oauth callback aliases failed", exc_info=True)

    try:
        _enforce_route_uniqueness(flask_app)
    except Exception:
        flask_app.logger.debug("Enforce route uniqueness failed", exc_info=True)

    try:
        _dedupe_rules(flask_app)
    except Exception:
        flask_app.logger.debug("Dedupe rules failed", exc_info=True)

    try:
        _stabilize_rules_order(flask_app)
    except Exception:
        flask_app.logger.debug("Stabilize rules order failed", exc_info=True)

    # Ensure DB tables when appropriate (before final rebuild so migrations can be checked)
    try:
        _ensure_db_tables(flask_app)
    except Exception:
        flask_app.logger.debug("ensure_db_tables failed", exc_info=True)

    # ------------------------------------------------------------------
    # FINAL AUTHORITATIVE REBUILD OF INTERNAL MAPS
    # ------------------------------------------------------------------
    try:
        _rebuild_rules_by_endpoint(flask_app)
    except Exception:
        flask_app.logger.debug("Final rebuild of rules_by_endpoint failed", exc_info=True)

    # ------------------------------------------------------------------
    # NON-DESTRUCTIVE ADMIN INDEX PRUNE (do not add rules here)
    # ------------------------------------------------------------------
    try:
        _ensure_admin_index_registered(flask_app)
    except Exception:
        flask_app.logger.debug("Ensure admin index registered failed", exc_info=True)

    # ------------------------------------------------------------------
    # FINAL STEP: REBUILD ADMIN_UI ALIASES AFTER HYGIENE (if present)
    # ------------------------------------------------------------------
    try:
        # Import alias registration helper lazily and safely (avoid import-time side effects)
        from importlib import import_module

        mod = import_module("app.blueprints.admin_ui_routes")
        _register_admin_ui_aliases = getattr(mod, "_register_admin_ui_aliases", None)
        # Only attempt alias synchronization if the admin blueprint is registered.
        if _register_admin_ui_aliases and "admin" in flask_app.blueprints:
            state = type("state", (), {"app": flask_app})
            _register_admin_ui_aliases(state)
            # Smoke verification log: counts of admin and admin_ui endpoints
            n_admin = sum(1 for k in flask_app.view_functions if k.startswith("admin."))
            n_alias = sum(1 for k in flask_app.view_functions if k.startswith("admin_ui."))
            flask_app.logger.info("Admin UI aliases re-synchronized. admin endpoints: %d, admin_ui aliases: %d", n_admin, n_alias)
        else:
            flask_app.logger.debug("admin_ui alias registration skipped (no helper or admin blueprint missing).")
    except Exception:
        flask_app.logger.debug("Rebuilding admin UI aliases failed", exc_info=True)

    # ------------------------------------------------------------------
    # SOCKETIO INITIALIZATION
    # ------------------------------------------------------------------
    try:
        socketio.init_app(flask_app)
        flask_app.logger.info("SocketIO initialized.")
    except Exception:
        flask_app.logger.debug("socketio.init_app failed", exc_info=True)

    # ------------------------------------------------------------------
    # REDIS CLIENT ATTACH
    # ------------------------------------------------------------------
    flask_app.redis_client = getattr(flask_app, "redis_client", None) or _maybe_redis_client

    # ------------------------------------------------------------------
    # Register diagnostics core routes (readyz/version/diagnostics/metrics, etc.)
    # ------------------------------------------------------------------
    try:
        _register_core_routes(flask_app)
    except Exception:
        flask_app.logger.debug("Register core routes failed", exc_info=True)

    # ------------------------------------------------------------------
    # TESTING‑ONLY DUMMY ENDPOINTS (required by smoketests)
    # ------------------------------------------------------------------
    if flask_app.config.get("TESTING"):
        try:
            @flask_app.route("/dummy_test_route", methods=["GET"])
            def dummy_test_route():
                return jsonify({"status": "ok", "mode": "testing"}), 200
            flask_app.logger.debug("Registered TESTING-only dummy endpoints: dummy_*")
        except Exception:
            flask_app.logger.debug("Failed to register TESTING-only dummy endpoints", exc_info=True)

    return flask_app



# =============================================================================
# Legacy shim compatibility
# =============================================================================
def legacy_get_app(*args, **kwargs) -> Flask:
    return create_app(*args, **kwargs)


get_app = legacy_get_app
__all__ = ["create_app"]
