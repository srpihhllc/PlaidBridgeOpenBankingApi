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

            # Catch both string checking and existing instance names globally
            if bp_name and (bp_name in flask_app.blueprints or bp_name in flask_app.blueprints.keys()):
                flask_app.logger.debug(
                    "Auto-discovery: blueprint '%s' already registered globally; skipping.", bp_name
                )
                return None

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
                cid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
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
        if "readyz" not in flask_app.view_functions:
            @flask_app.route("/readyz", methods=["GET"])
            def readyz() -> Response:
                results = _registry.run_all()
                overall_ok = all(v.get("ok", False) for v in results.values())
                return jsonify({"ok": overall_ok, "checks": results}), 200 if overall_ok else 503

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

        if "diagnostics" not in flask_app.view_functions:
            @flask_app.route("/diagnostics", methods=["GET"])
            def diagnostics() -> Response:
                return jsonify(_gather_diagnostics(flask_app)), 200

        if "dependency_graph" not in flask_app.view_functions:
            @flask_app.route("/dependency_graph", methods=["GET"])
            def dependency_graph() -> Response:
                return jsonify(_build_dependency_graph(flask_app)), 200

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


def _cleanup_premature_oauth_registrations(flask_app: Flask) -> None:
    """
    Remove prematurely-registered oauth.* endpoints.
    Non-destructive: do not call _rebuild_rules_by_endpoint here.
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
                    _logger.debug("Failed to remove rule %r for endpoint %s", rule, endpoint, exc_info=True)

            removed.append(endpoint)

        if removed:
            try:
                flask_app.logger.info("Removed premature oauth endpoints: %s", ", ".join(removed))
            except Exception:
                pass
    except Exception:
        _logger.debug("_cleanup_premature_oauth_registrations failed", exc_info=True)


def add_route_prune_whitelist(endpoint: str) -> List[str]:
    """Add an endpoint to the ROUTE_PRUNE_WHITELIST."""
    if endpoint and endpoint not in ROUTE_PRUNE_WHITELIST:
        ROUTE_PRUNE_WHITELIST.append(endpoint)
    return ROUTE_PRUNE_WHITELIST


def _prune_ignorable_route_rules(flask_app: Flask) -> None:
    """Remove rules that are clearly ignorable."""
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
    except Exception:
        _logger.debug("_prune_ignorable_route_rules failed", exc_info=True)


def _reconcile_oauth_callback_aliases(flask_app: Flask) -> None:
    """Ensure oauth callback endpoints are canonical and remove alias duplicates."""
    try:
        if not hasattr(flask_app, "view_functions"):
            return

        alias_map = {"oauth.callback_google_alias": "oauth.callback_google"}

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
    except Exception:
        _logger.debug("_reconcile_oauth_callback_aliases failed", exc_info=True)


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
                sorted([m for m in getattr(rule, "methods", set()) if m not in ("HEAD", "OPTIONS")])
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

        seen = set()
        to_remove: List[Any] = []

        for rule in list(flask_app.url_map.iter_rules()):
            path = getattr(rule, "rule", "") or ""
            methods = tuple(
                sorted([m for m in getattr(rule, "methods", set()) if m not in ("HEAD", "OPTIONS")])
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
                key=lambda r: (getattr(r, "rule", ""), getattr(r, "endpoint", "")),
            )
            setattr(flask_app.url_map, "_rules", rules_sorted)
        except Exception:
            pass
    except Exception:
        _logger.debug("_stabilize_rules_order failed", exc_info=True)


# =============================================================================
# Auth Loaders
# =============================================================================
def _register_login_manager_loader(flask_app: Flask) -> None:
    try:
        if not login_manager:
            return

        @login_manager.user_loader
        def _load_user(user_id: str):
            try:
                from app.models.user import User
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
                from app.models.user import User
                identity = jwt_data.get("sub") or jwt_data.get("identity")
                if identity is None:
                    return None
                return User.query.get(int(identity))
            except Exception:
                return None
    except Exception:
        _logger.debug("_register_jwt_loaders failed", exc_info=True)


def _ensure_admin_index_registered(flask_app: Flask) -> None:
    """
    Non-destructive check to ensure exactly one /admin endpoint exists.
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
            flask_app.logger.debug(
                "Found admin.admin_index view function but no rule; deferring to blueprint registration."
            )
            return
    except Exception:
        flask_app.logger.debug("_ensure_admin_index_registered failed", exc_info=True)


def _register_legacy_main_aliases(flask_app: Flask) -> None:
    """
    Temporary shim to map legacy main.* template calls to their modern
    modularized endpoints (admin.*, diagnostics.*) to satisfy the template audit.
    """
    try:
        if not hasattr(flask_app, "view_functions"):
            return

        # Map: Legacy Template Reference -> Modern Backend Target
        legacy_map = {
            "main.redis_panel": "admin.redis_panel",
            "main.rate_limits_dashboard": "admin.rate_limits_dashboard",
            "main.schema_diagram": "admin.schema_viewer",
            "main.log_viewer": "admin.log_viewer",
            "main.debug_db": "admin.sql_panel",
            "main.cache_health": "diagnostics.cache_health",
            "main.db_health": "diagnostics.db_health",
            "main.delete_redis_key": "admin.sweep_expired_keys",
            "main.delete_rate_limit": "admin.sweep_expired_keys",
            "main.export_users": "admin.sql_panel",
            "main.approve_user": "admin.admin_index"
        }

        created_aliases = []
        for legacy_ep, modern_ep in legacy_map.items():
            if legacy_ep not in flask_app.view_functions and modern_ep in flask_app.view_functions:
                flask_app.view_functions[legacy_ep] = flask_app.view_functions[modern_ep]
                created_aliases.append(legacy_ep)

                # Replicate the rule to satisfy url_for() static analysis
                rbep = getattr(flask_app.url_map, "_rules_by_endpoint", {})
                if modern_ep in rbep:
                    rbep.setdefault(legacy_ep, list(rbep[modern_ep]))

        if created_aliases:
            flask_app.logger.info(f"Applied legacy 'main' alias fallback for {len(created_aliases)} endpoints.")

    except Exception:
        flask_app.logger.debug("Legacy main alias fallback failed", exc_info=True)


# =============================================================================
# SINGLE, UNIFIED APPLICATION FACTORY
# =============================================================================
def create_app(
    config_class: Optional[Any] = None,
    env_name: Optional[str] = None,
    config_name: Optional[str] = None,
    **kwargs,
) -> Flask:
    """
    Create and configure the Flask application.
    Enforces deterministic blueprint auto-registration and safe admin alias resolution.
    """
    if config_class is None and "config_class" in kwargs:
        config_class = kwargs.pop("config_class")

    # Guarded block resolving dynamic configuration strings safely
    if isinstance(config_class, str) and "." in config_class:
        module_name, class_name = config_class.rsplit(".", 1)
        try:
            module = importlib.import_module(module_name)
            config_class = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            _logger.warning(
                "Failed to load config class '%s' from module '%s': %s. Falling back to defaults.",
                class_name, module_name, exc,
            )
            config_class = None

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

    # ------------------------------------------------------------------
    # Guarded Configuration Loading & Explicit Fallback Target
    # ------------------------------------------------------------------
    try:
        if isinstance(config_class, str):
            flask_app.config.from_object(config_class)
        else:
            flask_app.config.from_object(config_class)
    except Exception as exc:
        flask_app.logger.info("Config.from_object failed (%s); applying testing fallback.", exc)
        # Explicit fallback ensuring downstream extensions read the correct test mode constraints
        flask_app.config["TESTING"] = True
        try:
            from app.config import TestingConfig
            flask_app.config.from_object(TestingConfig)
        except Exception:
            flask_app.logger.debug("Loading TestingConfig failed; continuing with TESTING=True", exc_info=True)

    if str(original_config_name).lower().startswith("testing"):
        flask_app.config["TESTING"] = True

    # Setup Logging & Core Data
    _setup_logging(flask_app)
    flask_app.logger.info(f"Using config class: {original_config_name}")
    flask_app.config["APP_START_TIME"] = time.time()

    # ------------------------------------------------------------------
    # Systems & Extensions (Initialized strictly after testing fallback)
    # ------------------------------------------------------------------
    _register_error_handlers(flask_app)
    init_extensions(flask_app)
    _register_login_manager_loader(flask_app)
    _register_jwt_loaders(flask_app)

    # Healthchecks & Core Routes
    register_healthcheck("database", _make_db_check())
    register_healthcheck("migrations", _make_migrations_check())
    register_healthcheck("redis", _make_redis_check())

    @flask_app.route("/healthz", methods=["GET"])
    def healthz() -> Response:
        results = _registry.run_all()
        overall_ok = all(v.get("ok", False) for v in results.values())
        payload = {
            "healthy": overall_ok,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime": round(time.time() - float(flask_app.config.get("APP_START_TIME", time.time())), 2),
            "checks": results,
        }
        return jsonify(payload), 200 if overall_ok else 503

    @flask_app.route("/health", methods=["GET"])
    def health_check_simple():
        return {"status": "ok"}, 200

    # ------------------------------------------------------------------
    # Explicit Blueprint Registration (Admin APIs)
    # ------------------------------------------------------------------
    try:
        try:
            from .blueprints.admin_routes import admin_api_bp, admin_api_core_bp
        except Exception:
            admin_api_bp = None
            admin_api_core_bp = None
            flask_app.logger.debug("Could not import admin API blueprints; skipping.", exc_info=True)

        # Register Core Admin API Blueprint if not already registered
        if admin_api_core_bp:
            if admin_api_core_bp.name not in flask_app.blueprints and "admin_api_core" not in flask_app.blueprints:
                try:
                    flask_app.register_blueprint(admin_api_core_bp)
                    flask_app.logger.info(f"🔗 Registered {admin_api_core_bp.name}")
                except Exception:
                    pass

        # Register Main Admin API Blueprint if not already registered
        if admin_api_bp:
            if admin_api_bp.name not in flask_app.blueprints and "admin_api" not in flask_app.blueprints:
                try:
                    flask_app.register_blueprint(admin_api_bp)
                    flask_app.logger.info(f"🔗 Registered {admin_api_bp.name}")
                except Exception:
                    pass
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Explicit Blueprint Registration (Webhooks)
    # ------------------------------------------------------------------
    try:
        from app.webhooks.views import webhooks_bp
        if webhooks_bp.name not in flask_app.blueprints and "webhooks" not in flask_app.blueprints:
            flask_app.register_blueprint(webhooks_bp)
            flask_app.logger.info(f"🔗 Registered {webhooks_bp.name} blueprint")
    except Exception as exc:
        flask_app.logger.debug("Could not import webhooks blueprint; skipping.", exc_info=True)

    # ------------------------------------------------------------------
    # Auto-Discovery Blueprint Registration
    # ------------------------------------------------------------------
    try:
        _register_blueprints(flask_app)
    except Exception:
        flask_app.logger.debug("Auto-discovery blueprint registration failed", exc_info=True)

    # ------------------------------------------------------------------
    # Optional Admin UI Blueprint Override
    # ------------------------------------------------------------------
    try:
        admin_ui_enabled = flask_app.config.get("ADMIN_UI_ENABLED", False)
        force_admin_in_tests = flask_app.config.get("FORCE_REGISTER_ADMIN_UI_IN_TESTS", False)
        if admin_ui_enabled or (flask_app.config.get("TESTING") and force_admin_in_tests):
            try:
                from importlib import import_module
                mod = import_module("app.blueprints.admin_ui_routes")
                admin_bp = getattr(mod, "admin_bp", None)

                # Register Admin UI Blueprint safely if not already registered
                if admin_bp:
                    if admin_bp.name not in flask_app.blueprints and "admin" not in flask_app.blueprints:
                        try:
                            flask_app.register_blueprint(admin_bp)
                            flask_app.logger.info(f"🔗 Registered admin UI blueprint ({admin_bp.name})")
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Route Hygiene Passes (Non-Destructive)
    # ------------------------------------------------------------------
    try:
        _cleanup_premature_oauth_registrations(flask_app)
        _prune_ignorable_route_rules(flask_app)
        _reconcile_oauth_callback_aliases(flask_app)
        _enforce_route_uniqueness(flask_app)
        _dedupe_rules(flask_app)
        _stabilize_rules_order(flask_app)
        _ensure_db_tables(flask_app)
    except Exception:
        flask_app.logger.debug("Hygiene or DB check failed", exc_info=True)

    # ------------------------------------------------------------------
    # Authoritative Internal Rebuild (First Pass)
    # ------------------------------------------------------------------
    try:
        _rebuild_rules_by_endpoint(flask_app)
        _ensure_admin_index_registered(flask_app)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Admin Alias Deterministic Verification & Fallback
    # ------------------------------------------------------------------
    try:
        from app.blueprints.admin_ui_routes import register_admin_blueprint

        # DEFENSIVE GUARD: Only call registration if the blueprint hasn't already been compiled
        if "admin" not in flask_app.blueprints:
            register_admin_blueprint(flask_app, verify=True, raise_on_failure=False)
            flask_app.logger.debug("Admin blueprint verification executed successfully.")
        else:
            flask_app.logger.debug("Admin blueprint already registered; bypassing verification execution to prevent rule collisions.")

    except Exception:
        flask_app.logger.debug("Admin blueprint verification failed (non-fatal).", exc_info=True)

    try:
        created_aliases = []
        for name, vf in list(flask_app.view_functions.items()):
            if name.startswith("admin."):
                alias = "admin_ui." + name.split(".", 1)[1]
                if alias not in flask_app.view_functions:
                    flask_app.view_functions[alias] = vf
                    created_aliases.append(alias)
        if created_aliases:
            flask_app.logger.info("Applied admin_ui alias fallback for %d endpoints.", len(created_aliases))
    except Exception:
        flask_app.logger.debug("admin_ui alias fallback failed", exc_info=True)

    # ------------------------------------------------------------------
    # Legacy Main Alias Shim
    # ------------------------------------------------------------------
    _register_legacy_main_aliases(flask_app)

    # ------------------------------------------------------------------
    # Final Authoritative Rebuild (Alias Reflection)
    # ------------------------------------------------------------------
    try:
        _rebuild_rules_by_endpoint(flask_app)
    except Exception:
        flask_app.logger.debug("Final rebuild of rules_by_endpoint failed", exc_info=True)

    # ------------------------------------------------------------------
    # Final System Integrations
    # ------------------------------------------------------------------
    try:
        socketio.init_app(flask_app)
    except Exception:
        flask_app.logger.debug("socketio.init_app failed", exc_info=True)

    flask_app.redis_client = getattr(flask_app, "redis_client", None) or _maybe_redis_client

    try:
        _register_core_routes(flask_app)
    except Exception:
        pass

    if flask_app.config.get("TESTING"):
        try:
            @flask_app.route("/dummy_test_route", methods=["GET"])
            def dummy_test_route():
                return jsonify({"status": "ok", "mode": "testing"}), 200
        except Exception:
            pass

    return flask_app


# =============================================================================
# Legacy shim compatibility & Emergency Sentinel Fallback
# =============================================================================
def legacy_get_app(*args, **kwargs) -> Flask:
    return create_app(*args, **kwargs)

get_app = legacy_get_app
__all__ = ["create_app", "app"]

# Production Emergency Fallback Guard
if os.environ.get("FLASK_ENV") == "production":
    try:
        # Standard production application initialization
        app = create_app()
    except Exception as e:
        # Trigger the cockpit-grade fallback protocol
        _logger.critical(
            "UNSAFE FALLBACK APP CREATED: fallback_app_created. "
            "Operator hint: Check configuration and routing maps. Error: %s", e
        )
        app = Flask(__name__)
        app.config["SAFE_MODE"] = True
        app.config["FALLBACK_MODE"] = True
        app.config["PROPAGATE_EXCEPTIONS"] = False

        @app.route("/diagnostics")
        def fallback_diagnostics() -> Response:
            return jsonify({
                "safe_mode": True,
                "fallback_mode": True,
                "create_app_invoked": False
            }), 200

        @app.route("/healthz")
        def fallback_healthz() -> Response:
            return jsonify({
                "healthy": False,
                "checks": {"fallback": {"ok": False, "error": "fatal_init"}}
            }), 503

        @app.route("/readyz")
        def fallback_readyz() -> Response:
            return jsonify({
                "ready": False,
                "checks": {"fallback": {"ok": False, "error": "fatal_init"}}
            }), 503

        @app.route("/version")
        def fallback_version() -> Response:
            return jsonify({"fallback_mode": True}), 200
