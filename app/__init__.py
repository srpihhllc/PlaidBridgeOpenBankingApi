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
            "Blueprint registration/validation failed: %s", exc, exc_info=True
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
                return getattr(RevokedToken, "is_jti_blocklisted", lambda _j: False)(jti)
        except Exception:
            return False

    def _user_identity_lookup(identity):
        return str(identity)

    try:
        jwt.token_in_blocklist_loader(_check_if_token_is_revoked)
    except Exception:
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
    """
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

    try:
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names() or [])
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
    """
    try:
        if not hasattr(flask_app, "view_functions") or not hasattr(flask_app, "url_map"):
            return

        removed_any = False

        endpoints_to_remove = [
            ep for ep in list(flask_app.view_functions.keys()) if ep.startswith("oauth.")
        ]

        for ep in endpoints_to_remove:
            try:
                flask_app.view_functions.pop(ep, None)
                removed_any = True
            except Exception:
                _logger.debug("Failed to pop oauth endpoint %s from view_functions", ep, exc_info=True)

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
                        pass
        except Exception:
            _logger.debug("Failed while pruning url_map._rules for oauth endpoints", exc_info=True)

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
            try:
                setattr(flask_app.url_map, "_rules_by_endpoint", new_map)
            except Exception:
                _logger.debug("Could not set url_map._rules_by_endpoint, continuing", exc_info=True)
    except Exception:
        _logger.debug("Failed to rebuild _rules_by_endpoint", exc_info=True)

# The remainining content has not changed and is omitted for brevity...