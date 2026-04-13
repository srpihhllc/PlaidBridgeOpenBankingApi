# =============================================================================
# FILE: app/__init__.py
# DESCRIPTION: Hardened Flask application factory for PlaidBridgeOpenBankingApi.
# =============================================================================

"""
Hardened Flask application factory for PlaidBridgeOpenBankingApi.

Provides a stable, production-grade create_app() entrypoint and exposes
get_app() for legacy shim compatibility.

This module avoids module-level imports placed after executable code by
using a lazy loader for the legacy get_app shim. That prevents E402
("module level import not at top of file") while also avoiding circular
import issues at import time.

NOTE: This module intentionally mutates Werkzeug's internal url_map
structures (url_map._rules and url_map._rules_by_endpoint) in a small
number of places to support compatibility aliasing and deterministic
route pruning. Mutating these internals is fragile across Werkzeug/Flask
versions — any change to these functions should be accompanied by
test updates and careful review when upgrading Werkzeug/Flask.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import (
    Blueprint,
    Flask,
    Response,
    current_app,
    g,
    jsonify,
    request,
)
from sqlalchemy import inspect, text
from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.utils import ImportStringError, import_string

# Use package-local relative imports to avoid circular import issues during package init
from .config import get_config_class
from .extensions import (
    db,
    init_extensions,
    jwt,
    login_manager,
    socketio,
)

# Fallback defaults for some names that may be configured elsewhere in the package.
DEFAULT_ALLOW_PREMATURE_CLEANUP = True
# Must be mutable because tests/extensions append to it at import time
ROUTE_PRUNE_WHITELIST: List[str] = ["oauth.callback_google"]
_maybe_redis_client = None

_logger = logging.getLogger(__name__)


# =============================================================================
# Legacy shim compatibility (lazy import)
# =============================================================================


def _load_legacy_get_app() -> Callable[..., Flask]:
    # Local import avoids circular import at package init time
    from .flask_app import get_app as _get_app  # type: ignore

    return _get_app


def legacy_get_app(*args: Any, **kwargs: Any) -> Flask:
    """Lazy wrapper for the legacy get_app() function."""
    return _load_legacy_get_app()(*args, **kwargs)


# Backward-compatible alias for external callers that expect get_app()
get_app = legacy_get_app


# =============================================================================
# Internal helpers
# =============================================================================


def _safe_status_code(code: Any) -> int:
    try:
        return int(code)
    except Exception:
        return 500


def _register_blueprints(flask_app: Flask) -> None:
    try:
        from .blueprints import register_blueprints, validate_blueprints_graph

        register_blueprints(flask_app)
        validate_blueprints_graph(flask_app)
    except Exception as exc:
        flask_app.logger.error(
            "❌ Blueprint registration/validation failed: %s", exc, exc_info=True
        )
        raise


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

        # Translate certain client errors to more precise responses

        if status == 400 and isinstance(e, BadRequest):

            import traceback as _tb

            _logger.error(
                "BADREQUEST_PROBE type=%s desc=%r tb=\n%s",
                type(e).__name__,
                getattr(e, "description", None),
                _tb.format_exc(),
            )
            status = 422
            description = "Request body must be valid JSON"
            name = "Unprocessable Entity"

        # Hide internal details in production for 5xx errors
        if flask_app.config.get("ENV") == "production" and status >= 500:
            description = "The server encountered an internal error. Please try again later."
            name = "Internal Server Error"

        _logger.log(
            logging.WARNING if status < 500 else logging.ERROR,
            "HTTP %s (%s): %s",
            status,
            name,
            description,
            exc_info=(status >= 500),
        )

        payload = {"msg": name, "error": description}
        resp = jsonify(payload)
        resp.status_code = status
        return resp

    for code in (400, 401, 403, 404, 422, 500, 503):
        flask_app.register_error_handler(code, _handle_exception)
    flask_app.register_error_handler(HTTPException, _handle_exception)
    flask_app.register_error_handler(Exception, _handle_exception)


def _register_login_manager_loader(flask_app: Flask) -> None:
    @login_manager.user_loader
    def load_user(user_id):
        if user_id is None:
            return None
        try:
            from .models.user import User  # lazy import

            try:
                # try numeric id first
                return db.session.get(User, int(user_id))
            except (ValueError, TypeError):
                # non-numeric PKs are possible
                return db.session.get(User, user_id)
        except Exception as exc:
            _logger.warning("User loader failed for id=%s: %s", user_id, exc, exc_info=True)
            return None


def _register_jwt_loaders(flask_app: Flask) -> None:
    """
    Register JWT callbacks. Use decorators when available; set fallback attributes
    on the jwt object for environments where the decorator API isn't present.
    """

    def _check_if_token_is_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti") if isinstance(jwt_payload, dict) else None
        if not jti:
            return False
        try:
            from .models.revoked_token import RevokedToken  # lazy import

            try:
                return db.session.get(RevokedToken, jti) is not None
            except Exception:
                # Older model shapes may provide a classmethod/attribute
                return getattr(RevokedToken, "is_jti_blocklisted", lambda _j: False)(jti)
        except Exception:
            return False

    def _user_identity_lookup(identity):
        return str(identity)

    # Preferred: register via decorator if available
    try:
        jwt.token_in_blocklist_loader(_check_if_token_is_revoked)
    except Exception:
        # Fallback: attach a well-known attribute used by some consumers/tests
        try:
            setattr(jwt, "token_in_blocklist_callback", _check_if_token_is_revoked)
        except Exception:
            pass

    try:
        jwt.user_identity_loader(_user_identity_lookup)
    except Exception:
        try:
            setattr(jwt, "user_identity_callback", _user_identity_lookup)
        except Exception:
            pass

    # Defensive: ensure attributes exist for direct inspection
    try:
        if not getattr(jwt, "token_in_blocklist_callback", None):
            setattr(jwt, "token_in_blocklist_callback", _check_if_token_is_revoked)
    except Exception:
        pass
    try:
        if not getattr(jwt, "user_identity_callback", None):
            setattr(jwt, "user_identity_callback", _user_identity_lookup)
    except Exception:
        pass


def _ensure_db_tables(flask_app: Flask) -> None:
    """
    Best-effort creation of missing DB tables for tests and local development.

    In TESTING mode: import commonly-used model modules and call db.create_all()
    under the app context to guarantee a test schema.

    Outside TESTING: only create tables when a small set of essential tables are missing
    and ALEMBIC_RUNNING != "1".
    """
    # TESTING: try to ensure schema is fully present
    if flask_app.config.get("TESTING"):
        model_modules = [
            "app.models.trace_events",
            "app.models.user",
            "app.models.revoked_token",
        ]
        for mod in model_modules:
            try:
                importlib.import_module(mod)
            except Exception:
                _logger.debug("Model import skipped: %s", mod, exc_info=True)
        try:
            with flask_app.app_context():
                db.create_all()
            _logger.debug("db.create_all() completed for TESTING environment.")
        except Exception as exc:
            _logger.exception("db.create_all() failed in TESTING mode: %s", exc)
        return

    # Non-testing: conservative fallback only
    try:
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names() or [])

        # Minimal essential set used as a safe heuristic for non-test fallback.
        essential = {"users", "trace_events"}

        if not essential.issubset(existing):
            if os.getenv("ALEMBIC_RUNNING", "0") != "1":
                _logger.info(
                    "Essential tables missing (%s); calling db.create_all() as fallback.",
                    ", ".join(sorted(essential - existing)),
                )
                try:
                    db.create_all()
                except Exception as exc:
                    _logger.exception("db.create_all() fallback failed: %s", exc)
            else:
                _logger.debug(
                    "Essential tables missing (%s) but ALEMBIC_RUNNING=1; skipping create_all().",
                    ", ".join(sorted(essential - existing)),
                )
    except Exception as exc:
        _logger.debug("DB inspection fallback skipped: %s", exc)


def _cleanup_premature_oauth_registrations(flask_app: Flask) -> None:
    """
    Remove prematurely-registered oauth.* endpoints and their Rule objects.

    This aggressively removes endpoints whose name starts with "oauth." from
    flask_app.view_functions and prunes any corresponding Rule objects from
    url_map internals (_rules and _rules_by_endpoint). Rebuilds the
    _rules_by_endpoint mapping if internal structures were mutated.

    Always defensive and never raises out of this function.
    """
    try:
        if not hasattr(flask_app, "view_functions") or not hasattr(flask_app, "url_map"):
            return

        removed_any = False

        # Collect oauth.* endpoints present in view_functions
        endpoints_to_remove = [
            ep for ep in list(flask_app.view_functions.keys()) if ep.startswith("oauth.")
        ]

        # Remove entries from view_functions
        for ep in endpoints_to_remove:
            try:
                flask_app.view_functions.pop(ep, None)
                removed_any = True
            except Exception:
                _logger.debug("Failed to pop oauth endpoint %s from view_functions", ep, exc_info=True)

        # Remove Rule objects from internal _rules list when present
        try:
            if hasattr(flask_app.url_map, "_rules"):
                for rule in list(getattr(flask_app.url_map, "_rules", [])):
                    try:
                        if getattr(rule, "endpoint", "") in endpoints_to_remove:
                            try:
                                flask_app.url_map._rules.remove(rule)
                                removed_any = True
                            except ValueError:
                                pass
                    except Exception:
                        # tolerate odd Rule objects
                        pass
        except Exception:
            _logger.debug("Failed while pruning url_map._rules for oauth endpoints", exc_info=True)

        # Remove keys from _rules_by_endpoint mapping if present
        try:
            if hasattr(flask_app.url_map, "_rules_by_endpoint"):
                for ep in endpoints_to_remove:
                    try:
                        flask_app.url_map._rules_by_endpoint.pop(ep, None)
                        removed_any = True
                    except Exception:
                        pass
        except Exception:
            _logger.debug("Failed while pruning url_map._rules_by_endpoint for oauth endpoints", exc_info=True)

        # Rebuild _rules_by_endpoint mapping from remaining _rules for Werkzeug consistency
        if removed_any and hasattr(flask_app.url_map, "_rules") and hasattr(flask_app.url_map, "_rules_by_endpoint"):
            try:
                new_map: Dict[str, list] = {}
                for r in list(flask_app.url_map._rules):
                    new_map.setdefault(getattr(r, "endpoint", None), []).append(r)
                flask_app.url_map._rules_by_endpoint = new_map
            except Exception:
                _logger.debug("Failed to rebuild url_map._rules_by_endpoint after oauth cleanup", exc_info=True)
    except Exception:
        _logger.debug("oauth cleanup failed", exc_info=True)


# =============================================================================
# URL map mutation helpers (centralize fragile Werkzeug mutations)
# =============================================================================
def _rebuild_rules_by_endpoint(flask_app: Flask) -> None:
    """
    Rebuild the url_map._rules_by_endpoint mapping from the current rules list.

    NOTE: This mutates Werkzeug internals (url_map._rules_by_endpoint) and must be
    exercised with care. Tests cover behavior that depends on this mapping.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return
        rules_list = list(getattr(flask_app.url_map, "_rules", list(flask_app.url_map.iter_rules())))
        new_map: Dict[str, list] = {}
        for r in rules_list:
            new_map.setdefault(getattr(r, "endpoint", None), []).append(r)
        try:
            flask_app.url_map._rules_by_endpoint = new_map
        except Exception:
            # Some Werkzeug versions may treat this attr read-only; best-effort set
            try:
                setattr(flask_app.url_map, "_rules_by_endpoint", new_map)
            except Exception:
                _logger.debug("Could not set url_map._rules_by_endpoint, continuing", exc_info=True)
    except Exception:
        _logger.debug("Failed to rebuild _rules_by_endpoint", exc_info=True)


def _safe_remove_rule_obj(flask_app: Flask, rule_obj, endpoint_name: Optional[str] = None) -> None:
    """
    Safely remove a Rule object from url_map._rules and update _rules_by_endpoint.

    This centralizes the mutation and reduces duplicated try/except logic.
    """
    try:
        if not hasattr(flask_app, "url_map"):
            return
        umap = flask_app.url_map
        # Remove from _rules list if present
        if hasattr(umap, "_rules"):
            try:
                lst = getattr(umap, "_rules", None)
                if lst and rule_obj in lst:
                    lst.remove(rule_obj)
            except Exception:
                pass
        # Remove from mapping entry if present
        if hasattr(umap, "_rules_by_endpoint") and endpoint_name:
            try:
                mapping = getattr(umap, "_rules_by_endpoint", {}) or {}
                lst = mapping.get(endpoint_name)
                if lst:
                    try:
                        new_lst = [x for x in lst if x is not rule_obj]
                        if new_lst:
                            mapping[endpoint_name] = new_lst
                        else:
                            mapping.pop(endpoint_name, None)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        _logger.debug("safe_remove_rule_obj failed for endpoint %s", endpoint_name, exc_info=True)


def add_route_prune_whitelist(name: str) -> None:
    """
    Add a single endpoint prefix to the mutable route-prune whitelist.

    Tests and extensions expect to be able to call this at import time, so
    ROUTE_PRUNE_WHITELIST must be a mutable list. This function is idempotent.
    """
    if not isinstance(name, str):
        raise TypeError("whitelist name must be a string")
    try:
        if name not in ROUTE_PRUNE_WHITELIST:
            ROUTE_PRUNE_WHITELIST.append(name)
            _logger.debug("Added '%s' to ROUTE_PRUNE_WHITELIST", name)
    except Exception:
        _logger.debug("Failed to add '%s' to ROUTE_PRUNE_WHITELIST", name, exc_info=True)


# ============================================================================
# Health check registry so extensions can self-report
# ============================================================================
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
            if "latency_ms" not in res:
                res["latency_ms"] = 0.0
            return res
        except Exception as exc:
            _logger.debug("Health check '%s' raised: %s", name, exc, exc_info=True)
            return {"ok": False, "error": str(exc), "latency_ms": 0.0}

    def run_all(self) -> Dict[str, HealthCheckResult]:
        results: Dict[str, HealthCheckResult] = {}
        for name in sorted(self._checks.keys()):
            results[name] = self.run_check(name)
        return results

    def list_checks(self) -> Tuple[str, ...]:
        return tuple(sorted(self._checks.keys()))


_registry = HealthCheckRegistry()


def register_healthcheck(name: str, fn: HealthCheckFn) -> None:
    """Public helper for extensions to register checks."""
    _registry.register(name, fn)


def unregister_healthcheck(name: str) -> None:
    """Public helper to remove a previously-registered check."""
    _registry.unregister(name)


# ============================================================================
# Basic healthcheck factories
# ============================================================================
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
            pong = False
            if hasattr(rc, "ping"):
                pong = rc.ping()
            else:
                pong = True
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
                row = db.session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
                applied = bool(row and row[0])
                return {"ok": applied, "version": (row[0] if row else None), "latency_ms": 0.0}
            except Exception as exc:
                _logger.debug("Migrations check query failed: %s", exc, exc_info=True)
                return {"ok": False, "error": str(exc), "latency_ms": 0.0}
        except Exception as exc:
            _logger.debug("Migrations check failed: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc), "latency_ms": 0.0}

    return _migrations_check


# ============================================================================
# Structured logging with Correlation IDs
# ============================================================================
class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that injects a `correlation_id` attribute into the LogRecord.
    The correlation ID is taken from flask.g.correlation_id if available, else from
    the 'X-Correlation-ID' request header, else generated.
    """

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
    """
    Configure a simple structured-ish logger: logs are JSON-ish strings including
    timestamp, level, message, and correlation_id.
    """
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


# ============================================================================
# Helper utilities that operate on the app (routing, diagnostics, etc.)
# ============================================================================
def _gather_diagnostics(flask_app: Flask) -> Dict[str, Any]:
    diag: Dict[str, Any] = {}
    safe_keys = [
        "ENV",
        "APP_VERSION",
        "TESTING",
        "SQLALCHEMY_DATABASE_URI",
        "SQLALCHEMY_ENGINE_OPTIONS",
        "RATE_LIMIT_ENABLED",
        "LIMITER_DEFAULTS",
        "REDIS_URL",
    ]
    cfg = {}
    for k in safe_keys:
        v = flask_app.config.get(k)
        if k == "SQLALCHEMY_DATABASE_URI":
            cfg[k] = _mask_db_url(v) if v is not None else None
        elif k == "REDIS_URL":
            cfg[k] = "present" if v else None
        else:
            cfg[k] = v
    diag["config"] = cfg

    ext_info = {}
    try:
        for k, inst in (getattr(flask_app, "extensions", {}) or {}).items():
            ext_info[k] = {"present": True, "type": type(inst).__name__ if inst is not None else None}
    except Exception:
        ext_info = {"error": "failed_to_inspect_extensions"}
    diag["extensions"] = ext_info

    try:
        diag["blueprints"] = list(sorted(flask_app.blueprints.keys()))
    except Exception:
        diag["blueprints"] = []

    try:
        engine = db.engine
        diag["db_engine"] = {
            "dialect": getattr(engine, "name", None),
            "driver": getattr(getattr(engine, "dialect", None), "name", None),
            "pool": type(getattr(engine, "pool", None)).__name__ if getattr(engine, "pool", None) else None,
            "url": _mask_db_url(str(getattr(engine, "url", None))),
        }
    except Exception:
        diag["db_engine"] = {"error": "no_engine"}

    try:
        diag["healthchecks_registered"] = list(_registry.list_checks())
    except Exception:
        diag["healthchecks_registered"] = []

    return diag


def _mask_db_url(url_str: Optional[str]) -> Optional[str]:
    if not url_str:
        return None
    try:
        if "@" in url_str and "://" in url_str:
            prefix, rest = url_str.split("://", 1)
            if "@" in rest:
                creds, host = rest.split("@", 1)
                if ":" in creds:
                    user, _pw = creds.split(":", 1)
                    return f"{prefix}://{user}:****@{host}"
        return url_str
    except Exception:
        return "masked"


def _build_dependency_graph(flask_app: Flask) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    nodes.append({"id": "app", "label": "app", "type": "app"})
    try:
        for k in sorted((getattr(flask_app, "extensions", {}) or {}).keys()):
            nid = f"extension:{k}"
            nodes.append({"id": nid, "label": k, "type": "extension"})
            edges.append({"from": "app", "to": nid})
    except Exception:
        pass

    try:
        for bp in sorted(flask_app.blueprints.keys()):
            nid = f"blueprint:{bp}"
            nodes.append({"id": nid, "label": bp, "type": "blueprint"})
            edges.append({"from": "app", "to": nid})
    except Exception:
        pass

    dot_lines = ["digraph dependencies {"]
    for n in nodes:
        label = n["label"].replace('"', '\\"')
        dot_lines.append(f'  "{n["id"]}" [label="{label}", shape=box];')
    for e in edges:
        dot_lines.append(f'  "{e["from"]}" -> "{e["to"]}";')
    dot_lines.append("}")

    dot = "\n".join(dot_lines)

    return {"nodes": nodes, "edges": edges, "dot": dot}


# ============================================================================
# Routing validation & optional "route contract" export (collision-free policy)
# ============================================================================


def _find_route_collisions(flask_app: Flask):
    seen: Dict[Tuple[str, Tuple[str, ...]], str] = {}
    collisions: List[Dict[str, Any]] = []
    for rule in flask_app.url_map.iter_rules():
        methods = tuple(sorted(set(rule.methods or []) - {"HEAD", "OPTIONS"}))
        key = (rule.rule, methods)
        if key in seen:
            collisions.append(
                {
                    "rule": rule.rule,
                    "methods": list(rule.methods or []),
                    "existing_endpoint": seen[key],
                    "new_endpoint": rule.endpoint,
                }
            )
        else:
            seen[key] = rule.endpoint
    return collisions


def _is_ignorable_collision(existing_ep: str, new_ep: str, rule: str) -> bool:
    try:
        if not existing_ep or not new_ep:
            return False

        def split_ep(ep: str):
            if "." in ep:
                bp, fn = ep.split(".", 1)
            else:
                bp, fn = None, ep
            return bp, fn

        existing_bp, existing_fn = split_ep(existing_ep)
        new_bp, new_fn = split_ep(new_ep)

        if existing_bp and new_bp and existing_bp != new_bp:
            return False

        compat_suffixes = ("_clean", "_compat", "_legacy", "_old")
        compat_tokens = ("compat", "legacy", "clean", "shim")

        for s in compat_suffixes:
            if existing_fn == new_fn + s or new_fn == existing_fn + s:
                return True

        lower_e = existing_fn.lower()
        lower_n = new_fn.lower()
        for t in compat_tokens:
            if (t in lower_e or t in lower_n) and (
                (existing_bp == new_bp) or (existing_bp is None and new_bp is None)
            ):
                return True

        return False
    except Exception:
        return False


def _choose_compat_endpoint_to_remove(existing_ep: str, new_ep: str) -> Optional[str]:
    try:
        def split_fn(ep: str):
            return ep.split(".", 1)[1] if "." in ep else ep

        existing_fn = split_fn(existing_ep)
        new_fn = split_fn(new_ep)

        compat_suffixes = ("_clean", "_compat", "_legacy", "_old")
        compat_tokens = ("compat", "legacy", "clean", "shim")

        for s in compat_suffixes:
            if existing_fn.endswith(s) and not new_fn.endswith(s):
                return existing_ep
            if new_fn.endswith(s) and not existing_fn.endswith(s):
                return new_ep

        lower_e = existing_fn.lower()
        lower_n = new_fn.lower()
        for t in compat_tokens:
            if t in lower_e and t not in lower_n:
                return existing_ep
            if t in lower_n and t not in lower_e:
                return new_ep

        if len(existing_fn) > len(new_fn):
            return existing_ep
        if len(new_fn) > len(existing_fn):
            return new_ep

        return None
    except Exception:
        return None


def _prune_ignorable_route_rules(flask_app: Flask) -> None:
    """
    Remove ignorable/explicit compat rules that would create collisions.

    We aggressively prune any explicit rule objects for endpoints that:
      - have a URL rule under /callback/<...>
      - have an endpoint name that ends with '_clean' (compat alias)
    This ensures sentinel alias endpoints are visible via view_functions/_rules_by_endpoint
    or via HEAD/OPTIONS-only rule, but do not create duplicate GET/POST routes.
    """
    try:
        removed_any_global = False

        for r in list(getattr(flask_app.url_map, "_rules", list(flask_app.url_map.iter_rules()))):
            try:
                rule_path = getattr(r, "rule", "") or ""
                ep = getattr(r, "endpoint", "") or ""
                if rule_path.startswith("/callback/") and ep.endswith("_clean"):
                    _safe_remove_rule_obj(flask_app, r, ep)
                    removed_any_global = True
            except Exception:
                _logger.debug("Ignored malformed Rule while pruning compat rules", exc_info=True)

        collisions = _find_route_collisions(flask_app)
        if not collisions:
            if (
                removed_any_global
                and hasattr(flask_app.url_map, "_rules")
                and hasattr(flask_app.url_map, "_rules_by_endpoint")
            ):
                try:
                    _rebuild_rules_by_endpoint(flask_app)
                except Exception:
                    _logger.debug("Failed to rebuild url_map._rules_by_endpoint after compat pruning", exc_info=True)
            return

        for c in collisions:
            existing = c.get("existing_endpoint", "") or ""
            new = c.get("new_endpoint", "") or ""
            rule = c.get("rule", "")

            try:
                if (existing and existing.startswith("oauth.callback_")) or (new and new.startswith("oauth.callback_")):
                    _logger.debug("Skipping pruning decision for oauth callback collision: %s / %s at %s", existing, new, rule)
                    continue
            except Exception:
                pass

            if not _is_ignorable_collision(existing, new, rule):
                continue

            remove_ep = _choose_compat_endpoint_to_remove(existing, new)
            if not remove_ep:
                _logger.debug("Could not decide which compat endpoint to remove for collision %s: %s / %s", rule, existing, new)
                continue

            removed_any_for_collision = False
            for r in list(flask_app.url_map.iter_rules()):
                if (r.endpoint or "") != remove_ep or (r.rule or "") != rule:
                    continue
                try:
                    _safe_remove_rule_obj(flask_app, r, remove_ep)
                    removed_any_for_collision = True
                    removed_any_global = True
                except Exception:
                    _logger.debug("Failed to prune rule %s for endpoint %s", rule, remove_ep, exc_info=True)

            if removed_any_for_collision:
                _logger.info("Pruned ignorable route %s (removed endpoint %s) to avoid collision", rule, remove_ep)

        if removed_any_global and hasattr(flask_app.url_map, "_rules") and hasattr(flask_app.url_map, "_rules_by_endpoint"):
            try:
                _rebuild_rules_by_endpoint(flask_app)
            except Exception:
                _logger.debug("Failed to rebuild url_map._rules_by_endpoint after pruning", exc_info=True)

    except Exception:
        _logger.debug("Prune ignorable route rules encountered an error", exc_info=True)


def _reconcile_oauth_callback_aliases(flask_app: Flask) -> None:
    """
    Make compat endpoints visible for all /callback/<provider> routes.

    For each callback path found (rule starting with /callback/), prefer the
    canonical endpoint (oauth.callback_<provider>) and ensure an alias
    oauth.callback_<provider>_clean exists and is visible in iter_rules().

    To avoid route collisions we ensure the alias rule — if added — is HEAD/OPTIONS-only.
    """
    try:
        flask_app.logger.debug("Running oauth callback alias reconciliation (generic)")

        rules_list = list(getattr(flask_app.url_map, "_rules", list(flask_app.url_map.iter_rules())))
        cb_rules_by_path: Dict[str, List] = {}
        for r in rules_list:
            rule_path = getattr(r, "rule", "") or ""
            if rule_path.startswith("/callback/"):
                cb_rules_by_path.setdefault(rule_path, []).append(r)

        if not cb_rules_by_path:
            flask_app.logger.debug("No /callback/* rules found during reconciliation")
            return

        for callback_path, cb_rules in cb_rules_by_path.items():
            canonical_rule = next((r for r in cb_rules if (r.endpoint or "") == f"oauth.callback_{callback_path.split('/')[-1]}"), None)
            if canonical_rule is None:
                canonical_rule = next(
                    (r for r in cb_rules if (r.endpoint or "").endswith("callback_" + callback_path.split("/")[-1]) and not (r.endpoint or "").endswith("_clean")),
                    None,
                )
            if canonical_rule is None:
                canonical_rule = cb_rules[0]

            provider = callback_path.split("/")[-1]
            canonical_ep = f"oauth.callback_{provider}"
            compat_ep = f"{canonical_ep}_clean"

            view_fn = flask_app.view_functions.get(canonical_ep) or flask_app.view_functions.get(canonical_rule.endpoint)
            if view_fn is None:
                for r in cb_rules:
                    view_fn = flask_app.view_functions.get(r.endpoint)
                    if view_fn:
                        break
            if not view_fn:
                flask_app.logger.debug("No view function found for %s during reconciliation", callback_path)
                continue

            flask_app.view_functions.setdefault(canonical_ep, view_fn)
            flask_app.view_functions.setdefault(compat_ep, flask_app.view_functions[canonical_ep])

            for r in list(getattr(flask_app.url_map, "_rules", list(flask_app.url_map.iter_rules()))):
                try:
                    if (r.rule or "") == callback_path and (r.endpoint or "") == compat_ep:
                        methods = set(getattr(r, "methods", set()) or set())
                        non_safe = methods - {"HEAD", "OPTIONS"}
                        if non_safe:
                            _safe_remove_rule_obj(flask_app, r, compat_ep)
                except Exception:
                    pass

            has_compat_visible = any(
                (r.rule or "") == callback_path and (r.endpoint or "") == compat_ep
                for r in list(getattr(flask_app.url_map, "_rules", list(flask_app.url_map.iter_rules())))
            )
            if not has_compat_visible:
                try:
                    existing_vf = flask_app.view_functions.get(compat_ep)
                    if existing_vf and existing_vf is not view_fn:
                        flask_app.logger.warning(
                            "Compat endpoint %s already present in view_functions with a different callable; overwriting for compatibility",
                            compat_ep,
                        )
                    flask_app.add_url_rule(
                        callback_path,
                        endpoint=compat_ep,
                        view_func=view_fn,
                        methods=["HEAD", "OPTIONS"],
                    )
                    flask_app.logger.info("Added HEAD/OPTIONS-only compat rule for %s", compat_ep)
                except Exception:
                    flask_app.logger.exception("Failed adding HEAD/OPTIONS-only compat rule for %s", compat_ep)

        try:
            _rebuild_rules_by_endpoint(flask_app)
            flask_app.logger.info("Rebuilt url_map._rules_by_endpoint after callback alias reconciliation")
        except Exception:
            flask_app.logger.exception("Failed rebuilding _rules_by_endpoint during oauth alias reconciliation")

    except Exception:
        flask_app.logger.exception("OAuth callback alias reconciliation failed", exc_info=True)


def _enforce_route_uniqueness(flask_app: Flask) -> None:
    try:
        if not globals().get("_CREATE_APP_INVOKED", False) and not flask_app.config.get("TESTING", False):
            _logger.debug("Route uniqueness enforcement skipped: create_app() sentinel not set and not TESTING")
            return

        if not flask_app.config.get("ALLOW_PREMATURE_CLEANUP", DEFAULT_ALLOW_PREMATURE_CLEANUP):
            _logger.debug("Route uniqueness enforcement skipped by ALLOW_PREMATURE_CLEANUP flag")
            return

        rules_by_key: Dict[Tuple[str, Tuple[str, ...]], list] = {}
        for r in list(flask_app.url_map.iter_rules()):
            methods = tuple(sorted(set(r.methods or []) - {"HEAD", "OPTIONS"}))
            key = (r.rule, methods)
            rules_by_key.setdefault(key, []).append(r)

        removed_total = 0
        whitelist = tuple(ROUTE_PRUNE_WHITELIST)

        for _, rules in rules_by_key.items():
            if len(rules) <= 1:
                continue

            primary = rules[0]
            primary_ep = getattr(primary, "endpoint", "") or ""
            if any(primary_ep.startswith(w) for w in whitelist):
                continue

            duplicates = [r for r in rules[1:] if (r.endpoint or "") == primary_ep]
            for r in duplicates:
                try:
                    _safe_remove_rule_obj(flask_app, r, primary_ep)
                    removed_total += 1
                except Exception:
                    _logger.debug("Failed to prune duplicate route for endpoint %s", primary_ep, exc_info=True)

        if removed_total and hasattr(flask_app.url_map, "_rules") and hasattr(flask_app.url_map, "_rules_by_endpoint"):
            try:
                _rebuild_rules_by_endpoint(flask_app)
            except Exception:
                _logger.debug("Failed to rebuild url_map._rules_by_endpoint after uniqueness enforcement", exc_info=True)

        if removed_total:
            _logger.info("Pruned %d duplicate route rule(s) to enforce uniqueness", removed_total)

    except Exception:
        _logger.debug("Route uniqueness enforcement failed", exc_info=True)


# ============================================================================
# Application factory
# ============================================================================
def create_app(env_name: str = None, config_class=None) -> Flask:
    # Sentinel for fallback logic — set as early as possible so import-time
    # fallback detection cannot mistakenly create the unsafe fallback app.
    try:
        globals()["_CREATE_APP_INVOKED"] = True
    except Exception:
        pass

    package_root = Path(__file__).resolve().parent
    flask_app = Flask(
        "flask_app",
        template_folder=str(package_root / "templates"),
        static_folder=str(package_root / "static"),
    )

    # --------------------------
    # Resolve config_class input
    # --------------------------
    if isinstance(config_class, str):
        try:
            config_class = import_string(config_class)
        except ImportStringError:
            try:
                config_class = import_string(f"app.config.{config_class}")
            except ImportStringError:
                _logger.exception("Failed to import config '%s'", config_class)
                raise

    # Load configuration
    if config_class:
        flask_app.config.from_object(config_class)
        try:
            provided_name = getattr(config_class, "__name__", None) or getattr(type(config_class), "__name__", None)
            _logger.info("Config class (provided) name: %s", provided_name)
            if provided_name and ("test" in provided_name.lower() or "testing" in provided_name.lower()):
                _logger.info("Config class (alias): TestConfig")
        except Exception:
            _logger.debug("Failed to log provided config class name", exc_info=True)
    else:
        cfg = get_config_class(env_name)
        flask_app.config.from_object(cfg)
        try:
            resolved_name = getattr(cfg, "__name__", None) or getattr(type(cfg), "__name__", None)
            _logger.info("Config class (resolved) name: %s", resolved_name)
            if resolved_name and ("dev" in resolved_name.lower() or "development" in resolved_name.lower()):
                _logger.info("Config class (alias): DevelopmentConfig")
        except Exception:
            _logger.debug("Failed to log resolved config class name", exc_info=True)

    # Force TestingConfig when running tests
    if flask_app.config.get("TESTING"):
        try:
            from .config import TestingConfig

            flask_app.config.from_object(TestingConfig)
        except Exception:
            pass
        flask_app.config["SECRET_KEY"] = "test-secret"
        flask_app.config["TEMPLATES_AUTO_RELOAD"] = True
        flask_app.jinja_env.cache = {}

    # Ensure the ALLOW_PREMATURE_CLEANUP setting is present (explicit preference)
    flask_app.config.setdefault("ALLOW_PREMATURE_CLEANUP", DEFAULT_ALLOW_PREMATURE_CLEANUP)

    # Structured logging & correlation header
    @flask_app.before_request
    def _assign_correlation_id():
        cid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
        if not cid:
            cid = f"cid-{uuid.uuid4().hex[:12]}"
        try:
            g.correlation_id = cid
        except Exception:
            pass

    @flask_app.after_request
    def _add_correlation_to_response(response):
        try:
            cid = getattr(g, "correlation_id", None)
            if cid:
                response.headers["X-Correlation-ID"] = cid
        except Exception:
            pass
        return response

    # Maintenance guard
    @flask_app.before_request
    def check_for_maintenance():
        if flask_app.config.get("MAINTENANCE_MODE"):
            allowed_paths = [
                "/diagnostics",
                "/static",
                "/admin",
                "/healthz",
                "/readyz",
                "/metrics",
                "/version",
            ]
            if not any(request.path.startswith(path) for path in allowed_paths):
                return (
                    jsonify(
                        {
                            "msg": "Service Unavailable",
                            "error": "The system is currently undergoing scheduled maintenance.",
                            "app_version": flask_app.config.get("APP_VERSION"),
                        }
                    ),
                    503,
                )

    # SQLAlchemy engine tuning
    uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri and uri.startswith("sqlite"):
        flask_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"poolclass": None}
    else:
        flask_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
        }

    @flask_app.context_processor
    def inject_view_functions():
        return {"view_functions": flask_app.view_functions}

    flask_app.config.setdefault("APP_START_TIME", time.time())
    flask_app.start_time = flask_app.config.get("APP_START_TIME")

    # Initialize extensions
    init_extensions(flask_app)

    # Expose managers
    try:
        flask_app.jwt_manager = jwt
    except Exception:
        pass
    try:
        flask_app.login_manager = login_manager
    except Exception:
        pass

    # Initialize limiter
    try:
        from . import extensions as _extensions

        limiter_instance = getattr(_extensions, "limiter", None) or globals().get("limiter", None)
        if limiter_instance and hasattr(limiter_instance, "init_app"):
            limiter_instance.init_app(flask_app)
            flask_app.logger.info("⏱️ Limiter initialized via init_app()")
        else:
            flask_app.logger.info("⏱️ No limiter instance available to init; skipping.")
    except Exception as exc:
        flask_app.logger.error("Failed to init limiter: %s", exc, exc_info=True)

    # Import models
    try:
        from . import models  # noqa: F401
    except Exception:
        flask_app.logger.debug("models package import failed or deferred", exc_info=True)

    # Ensure specific model modules are imported before calling db.create_all().
    try:
        from .models import trace_events  # noqa: F401
    except Exception:
        flask_app.logger.debug("trace_events model import failed", exc_info=True)

    # Best-effort ensure DB tables AFTER models are imported so SQLAlchemy metadata is available.
    try:
        _ensure_db_tables(flask_app)
        flask_app.logger.debug("Called _ensure_db_tables() to create missing tables if needed.")
    except Exception:
        flask_app.logger.debug("Fallback db.create_all() skipped or failed", exc_info=True)

    # JWT loaders, logging, error handlers
    _register_jwt_loaders(flask_app)
    _setup_logging(flask_app)
    _register_error_handlers(flask_app)
    _register_login_manager_loader(flask_app)

    # Defensive: remove any oauth.* endpoints that were registered prematurely
    try:
        cleanup = globals().get("_cleanup_premature_oauth_registrations")
        if callable(cleanup):
            cleanup(flask_app)
    except Exception:
        flask_app.logger.debug("Pre-blueprint oauth cleanup failed", exc_info=True)

    # ============================================================================
    # BLUEPRINT REGISTRATION — FIXED ORDER
    # ============================================================================

    # 2. Admin blueprints (explicit ordering)
    try:
        from .blueprints.admin_routes import admin_api_bp, admin_bp as admin_api_core_bp
        from .blueprints.admin_ui_routes import admin_bp as admin_ui_bp

        flask_app.register_blueprint(admin_api_core_bp)  # name="admin_api_core", url_prefix=/admin/api
        flask_app.register_blueprint(admin_api_bp)       # name="admin_api",      url_prefix=/admin/api/v1
        flask_app.register_blueprint(admin_ui_bp)        # name="admin",          url_prefix=/admin (has admin_index)
    except Exception as exc:
        flask_app.logger.error("Failed to register admin blueprints: %s", exc, exc_info=True)

    # 3. Tiles blueprint
    try:
        from .routes.tiles import tiles_bp

        flask_app.register_blueprint(tiles_bp)
    except Exception as exc:
        flask_app.logger.warning("Tiles blueprint not loaded: %s", exc, exc_info=True)

    # 4. Auto-discovered blueprints (includes api_v1_bp with 404 handler)
    _register_blueprints(flask_app)

    # 5. Cockpit blueprints (drilldown, telemetry dashboard, trace, fk_inspector).
    #    These live under app/cockpit/ and are NOT auto-discovered by
    #    _register_blueprints() which only scans app/blueprints/.
    try:
        from .cockpit import register_cockpit_tiles

        register_cockpit_tiles(flask_app)
        flask_app.logger.info("✅ Cockpit tiles registered.")
    except Exception as exc:
        flask_app.logger.error(
            "Failed to register cockpit tiles: %s", exc, exc_info=True
        )

    # 6. Webhooks blueprint (ACH, Plaid, Reconcile listeners).
    #    Lives under app/webhooks/views.py — not auto-discovered.
    try:
        from .webhooks.views import webhooks_bp

        if "webhooks" not in flask_app.blueprints:
            flask_app.register_blueprint(webhooks_bp)
            flask_app.logger.info("🔗 Registered blueprint: webhooks_bp (url_prefix=/webhooks)")
        else:
            flask_app.logger.debug("webhooks_bp already registered; skipping.")
    except Exception as exc:
        flask_app.logger.error("Failed to register webhooks blueprint: %s", exc, exc_info=True)

    # Defensive: ensure any Blueprint objects exported by oauth_routes get registered.
    try:
        if "oauth" not in flask_app.blueprints:
            for mod_name in ("app.blueprints.oauth_routes", "app.routes.oauth_routes"):
                try:
                    mod = importlib.import_module(mod_name)
                except Exception:
                    continue

                for name in dir(mod):
                    try:
                        obj = getattr(mod, name)
                        if isinstance(obj, Blueprint):
                            bp_name = getattr(obj, "name", None)
                            if bp_name and bp_name not in flask_app.blueprints:
                                flask_app.register_blueprint(obj)
                                flask_app.logger.info("Registered blueprint: %s from %s", bp_name, mod_name)
                    except Exception:
                        flask_app.logger.debug("Failed to inspect/register obj '%s' from %s", name, mod_name, exc_info=True)

                if "oauth" in flask_app.blueprints:
                    break
    except Exception:
        flask_app.logger.debug("Defensive oauth_routes import/registration skipped or failed", exc_info=True)

    # Test/compat blueprint registration (DEFERRED)
    try:
        from app.blueprints.compat_routes import compat_bp

        compat_name = getattr(compat_bp, "name", None)
        if compat_name and compat_name in flask_app.blueprints:
            flask_app.logger.debug("compat_bp already registered as '%s'; skipping compat registration", compat_name)
        else:
            try:
                flask_app.register_blueprint(compat_bp)
                flask_app.logger.info("Registered compatibility blueprint: compat_bp")
            except Exception:
                flask_app.logger.debug("Failed to register compat_bp", exc_info=True)
    except Exception:
        flask_app.logger.debug("compat_routes import skipped or failed; compat_bp not registered", exc_info=True)

    # ------------------------------------------------------------------------
    # FINAL ROUTE CLEANUP / RECONCILIATION (single consolidated pass)
    # Order is important and deterministic:
    #   1) prune ignorable explicit compat rules
    #   2) reconcile oauth callback aliases (adds HEAD/OPTIONS-only compat rules)
    #   3) enforce uniqueness (remove duplicates not on whitelist)
    #   4) re-inject any admin.* rules dropped by the rebuild
    # Each step is guarded so failures are logged but do not abort startup.
    # ------------------------------------------------------------------------
    try:
        try:
            _prune_ignorable_route_rules(flask_app)
        except Exception:
            flask_app.logger.debug("Route pruning encountered an error", exc_info=True)

        try:
            _reconcile_oauth_callback_aliases(flask_app)
        except Exception:
            flask_app.logger.debug("OAuth alias reconciliation encountered an error", exc_info=True)

        try:
            _enforce_route_uniqueness(flask_app)
        except Exception:
            flask_app.logger.debug("Route uniqueness enforcement encountered an error", exc_info=True)

        # Step 4 — re-inject admin.* entries dropped by _rebuild_rules_by_endpoint.
        try:
            rbep = getattr(flask_app.url_map, "_rules_by_endpoint", None)
            if rbep is not None:
                for ep in list(flask_app.view_functions):
                    if ep.startswith("admin.") and ep not in rbep:
                        matching = [r for r in flask_app.url_map.iter_rules() if r.endpoint == ep]
                        if matching:
                            rbep[ep] = matching
                            flask_app.logger.debug(
                                "Re-injected dropped admin rule into _rules_by_endpoint: %s", ep
                            )
        except Exception:
            flask_app.logger.debug("admin _rules_by_endpoint preservation failed", exc_info=True)

    except Exception:
        flask_app.logger.debug("Final route cleanup encountered an unexpected error", exc_info=True)

    # ── admin_index direct registration (POST-CLEANUP) ────────────────────────
    # Must run AFTER all cleanup/rebuild passes — those passes can remove Rules
    # that live outside url_map._rules. Registering here is the last write to
    # url_map before the app is returned so the entry will be preserved.
    try:
        from app.blueprints.admin_ui_routes import admin_index as _admin_index_view

        # Ensure view_functions has the canonical mapping so url_for() resolves.
        try:
            if "admin.admin_index" not in flask_app.view_functions:
                flask_app.view_functions["admin.admin_index"] = _admin_index_view
        except Exception:
            # non-fatal; continue to attempt to add a Rule below
            flask_app.logger.debug("Could not ensure admin.admin_index in view_functions", exc_info=True)

        # Add a visible Rule only if none exists for the canonical endpoint
        has_rule = any(getattr(r, "endpoint", None) == "admin.admin_index" for r in flask_app.url_map.iter_rules())
        if not has_rule:
            try:
                flask_app.add_url_rule(
                    "/admin",
                    endpoint="admin.admin_index",
                    view_func=_admin_index_view,
                    strict_slashes=False,
                )
                flask_app.logger.info("Registered admin.admin_index directly on app at /admin (post-cleanup)")
            except Exception:
                flask_app.logger.exception("Failed to add Rule for admin.admin_index (post-cleanup)")
    except Exception as exc:
        flask_app.logger.error("Failed to register admin.admin_index directly (post-cleanup): %s", exc, exc_info=True)

    # Diagnostics
    @flask_app.route("/diagnostics", methods=["GET"])
    def diagnostics():
        fmt = request.args.get("format", "json").lower()
        diag = _gather_diagnostics(flask_app)
        dep = _build_dependency_graph(flask_app)
        diag["dependency_graph"] = {"nodes": dep["nodes"], "edges": dep["edges"]}
        if fmt == "dot":
            return Response(dep["dot"], mimetype="text/plain")
        return jsonify(diag)

    @flask_app.route("/dependency-graph", methods=["GET"])
    def dependency_graph():
        dep = _build_dependency_graph(flask_app)
        if request.args.get("format", "").lower() == "dot":
            return Response(dep["dot"], mimetype="text/plain")
        return jsonify(dep)

    # Return the fully-configured app instance
    return flask_app


# -----------------------------------------------------------------------------
# Final fallback guard — append this EXACT block at the very end of app/__init__.py
# Activates only when FLASK_ENV == "production" AND create_app() was NOT invoked.
# Does NOT overwrite an existing module-level `app` created by create_app().
# -----------------------------------------------------------------------------
_fallback_logger = globals().get("_logger") or logging.getLogger(__name__)

_create_app_invoked = bool(globals().get("_CREATE_APP_INVOKED", False))
if os.getenv("PYTEST_CURRENT_TEST"):
    _create_app_invoked = True
if os.getenv("FLASK_ENV") == "production":
    _create_app_invoked = False

if os.getenv("FLASK_ENV") == "production" and not _create_app_invoked:
    try:
        from flask import Flask as _Flask, jsonify as _jsonify

        fallback_app = _Flask("fallback_app")

        try:
            fallback_app.config["PROPAGATE_EXCEPTIONS"] = False
            fallback_app.config["TESTING"] = False
        except Exception:
            pass

        try:
            init_extensions(fallback_app)
        except Exception:
            try:
                if hasattr(jwt, "init_app"):
                    jwt.init_app(fallback_app)
            except Exception:
                pass
            try:
                if hasattr(login_manager, "init_app"):
                    login_manager.init_app(fallback_app)
            except Exception:
                pass
            try:
                from . import extensions as _extensions

                _limiter = getattr(_extensions, "limiter", None) or globals().get("limiter", None)
                if _limiter and hasattr(_limiter, "init_app"):
                    _limiter.init_app(fallback_app)
            except Exception:
                pass

        try:
            _register_jwt_loaders(fallback_app)
        except Exception:
            pass
        try:
            _register_login_manager_loader(fallback_app)
        except Exception:
            pass

        try:
            fallback_app.jwt_manager = jwt
        except Exception:
            pass
        try:
            fallback_app.login_manager = login_manager
        except Exception:
            pass

        fallback_app.config["SAFE_MODE"] = True
        fallback_app.config["FALLBACK_MODE"] = True

        _diagnostic_payload = {
            "event": "fallback_app_created",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "safe_mode": True,
            "fallback_mode": True,
            "create_app_invoked": _create_app_invoked,
            "reason": "FLASK_ENV=production at import time",
        }

        try:
            _fallback_logger.critical("UNSAFE FALLBACK APP CREATED")
        except Exception:
            pass
        try:
            logging.getLogger().critical("UNSAFE FALLBACK APP CREATED")
        except Exception:
            pass

        try:
            _msg = "Fallback diagnostics: %s" % (json.dumps(_diagnostic_payload, sort_keys=True))
            _fallback_logger.critical(_msg)
            logging.getLogger().critical(_msg)
        except Exception:
            pass

        try:
            _fallback_logger.critical(
                "Operator hint: This fallback app indicates FLASK_ENV=production was set before create_app() was invoked. "
                "Ensure your WSGI server calls create_app() and does not import the package root directly."
            )
            logging.getLogger().critical(
                "Operator hint: This fallback app indicates FLASK_ENV=production was set before create_app() was invoked. "
                "Ensure your WSGI server calls create_app() and does not import the package root directly."
            )
        except Exception:
            pass

        try:
            _fallback_logger.critical("WARNING: create_app() was never invoked — running in SAFE MODE fallback.")
            logging.getLogger().critical("WARNING: create_app() was never invoked — running in SAFE MODE fallback.")
        except Exception:
            pass

        @fallback_app.route("/diagnostics", methods=["GET"])
        def _fallback_diagnostics():
            return _jsonify(_diagnostic_payload), 200

        @fallback_app.route("/healthz")
        def _fallback_healthz():
            return _jsonify(
                {
                    "healthy": False,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "uptime": 0,
                    "checks": {"fallback": {"ok": False, "reason": "fallback_mode"}},
                }
            ), 503

        @fallback_app.route("/readyz")
        def _fallback_readyz():
            return _jsonify({"ready": False, "checks": {"fallback": {"ok": False, "reason": "fallback_mode"}}}), 503

        @fallback_app.route("/version")
        def _fallback_version():
            return _jsonify({"version": None, "fallback_mode": True}), 200

        @fallback_app.route("/openapi.json")
        def _fallback_openapi():
            return _jsonify(
                {
                    "openapi": "3.0.0",
                    "info": {
                        "title": "Fallback Mode API",
                        "version": "0.0.0-fallback",
                        "description": "Fallback-mode OpenAPI stub. create_app() was never invoked.",
                    },
                    "paths": {
                        "/healthz": {"get": {"summary": "Fallback healthz", "responses": {"503": {}}}},
                        "/readyz": {"get": {"summary": "Fallback readyz", "responses": {"503": {}}}},
                        "/diagnostics": {"get": {"summary": "Fallback diagnostics", "responses": {"200": {}}}},
                        "/version": {"get": {"summary": "Fallback version", "responses": {"200": {}}}},
                    },
                }
            ), 200

        @fallback_app.route("/metrics")
        def _fallback_metrics():
            lines = [
                "# HELP app_up 1 = healthy, 0 = unhealthy",
                "# TYPE app_up gauge",
                "app_up 0",
                "# HELP fallback_mode Indicates fallback mode is active",
                "# TYPE fallback_mode gauge",
                "fallback_mode 1",
                "# HELP create_app_invoked Whether create_app() was invoked",
                "# TYPE create_app_invoked gauge",
                f"create_app_invoked {1 if _create_app_invoked else 0}",
            ]
            return fallback_app.response_class("\n".join(lines) + "\n", mimetype="text/plain")

        @fallback_app.after_request
        def _fallback_html_banner(response):
            try:
                if response.mimetype == "text/html":
                    banner = (
                        "<div style='background:#b30000;color:white;padding:8px;"
                        "font-family:monospace;font-size:14px;'>"
                        "⚠ SAFE MODE: Fallback application active — create_app() was never invoked."
                        "</div>"
                    )
                    body = response.get_data(as_text=True)
                    response.set_data(banner + body)
            except Exception:
                pass
            return response

        def fallback_wsgi_app(environ, start_response):
            return fallback_app.wsgi_app(environ, start_response)

        if "app" not in globals():
            globals()["app"] = fallback_app
            globals()["_FALLBACK_CREATED"] = True

    except Exception as _exc:
        _fallback_logger.critical("FAILED TO CREATE UNSAFE FALLBACK APP: %s", _exc, exc_info=True)


# Public API exports
__all__ = [
    "create_app",
    "get_app",
    "legacy_get_app",
    "socketio",
    "_cleanup_premature_oauth_registrations",
    "add_route_prune_whitelist",
    "register_healthcheck",
    "unregister_healthcheck",
]
