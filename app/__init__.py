# =============================================================================
# Hardened Flask application factory.
# =============================================================================

"""
Hardened Flask application factory.

This file contains the canonical create_app factory. It intentionally avoids
importing application models at module import time to prevent duplicate SQLAlchemy
registrations when the package is imported under multiple roots.
"""

from __future__ import annotations
import logging
import os
import time
from pathlib import Path

from flask import Flask, jsonify, request
from sqlalchemy import inspect
from werkzeug.exceptions import BadRequest, HTTPException

# Use package-relative imports so `from app import create_app` resolves config
# and extensions relative to the imported package instance regardless of PYTHONPATH.
from .config import get_config_class
from .extensions import (
    db,
    init_extensions,
    jwt,
    login_manager,
    socketio,  # exposed at package level for `from app import socketio`
)

__all__ = ["create_app", "socketio"]

_logger = logging.getLogger(__name__)


# =============================================================================
# Logging (PythonAnywhere‑safe)
# =============================================================================
def _setup_logging(flask_app: Flask) -> None:
    flask_app.logger.setLevel(logging.INFO)


# =============================================================================
# Helpers
# =============================================================================
def _safe_status_code(code) -> int:
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
    def _handle_exception(e):
        if isinstance(e, HTTPException):
            status = _safe_status_code(e.code)
            description = getattr(e, "description", str(e))
            name = getattr(e, "name", "HTTPException")
        else:
            status = 500
            description = str(e)
            name = type(e).__name__

        if status == 400 and isinstance(e, BadRequest):
            status = 422
            description = "Request body must be valid JSON"
            name = "Unprocessable Entity"

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
    # Import User lazily to avoid importing models at package-import time
    @login_manager.user_loader
    def load_user(user_id):
        if user_id is None:
            return None
        try:
            from .models.user import User  # local import (package-relative)
            return db.session.get(User, int(user_id))
        except ValueError:
            try:
                from .models.user import User  # local import (package-relative)
                return db.session.get(User, user_id)
            except Exception:
                return None
        except Exception as exc:
            _logger.warning("User loader failed for id=%s: %s", user_id, exc, exc_info=True)
            return None


def _register_jwt_loaders(flask_app: Flask) -> None:
    # Import RevokedToken lazily to avoid model registration at import time
    @jwt.token_in_blocklist_loader
    def check_if_token_is_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        if not jti:
            return False
        from .models.revoked_token import RevokedToken  # local import (package-relative)
        return db.session.get(RevokedToken, jti) is not None

    @jwt.user_identity_loader
    def user_identity_lookup(identity):
        return str(identity)  # return string for JWT subject compatibility


def _ensure_db_tables(flask_app: Flask) -> None:
    try:
        inspector = inspect(db.engine)
        if "users" not in set(inspector.get_table_names()):
            _logger.info("Essential tables missing; calling db.create_all() as fallback.")
            db.create_all()
    except Exception as exc:
        _logger.debug("DB inspection fallback skipped: %s", exc)


# =============================================================================
# Application factory
# =============================================================================
def create_app(env_name: str = None, config_class=None) -> Flask:
    package_root = Path(__file__).resolve().parent
    flask_app = Flask(
        "flask_app",
        template_folder=str(package_root / "templates"),
        static_folder=str(package_root / "static"),
    )

    # 1. Load configuration
    if config_class:
        flask_app.config.from_object(config_class)
    else:
        cfg = get_config_class(env_name)
        flask_app.config.from_object(cfg)

    # -------------------------------------------------------------------------
    # Force TestingConfig when running tests (SQLite in-memory)
    # ⭐ CRITICAL: Must happen BEFORE init_extensions() so limiter sees TESTING=True
    # -------------------------------------------------------------------------
    if flask_app.config.get("TESTING"):
        from .config import TestingConfig

        flask_app.config.from_object(TestingConfig)
        flask_app.config["SECRET_KEY"] = "test-secret"
        flask_app.config["TEMPLATES_AUTO_RELOAD"] = True
        flask_app.jinja_env.cache = {}

    # -------------------------------------------------------------------------
    # ⭐ MAINTENANCE MODE GUARD (Gatekeeper)
    # -------------------------------------------------------------------------
    @flask_app.before_request
    def check_for_maintenance():
        if flask_app.config.get("MAINTENANCE_MODE"):
            allowed_paths = ["/diagnostics", "/static", "/admin"]
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

    # 3. SQLAlchemy engine tuning
    uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
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

    flask_app.start_time = time.time()

    # 4. Initialize extensions (NOW after TESTING config is set)
    init_extensions(flask_app)

    # Register all models so SQLAlchemy mappings exist for test collection and imports.
    # Do this after extensions are initialized so `db` is bound to the app.
    import .models  # noqa: F401 - package-relative import ensures correct module resolution

    # 5. JWT loaders
    _register_jwt_loaders(flask_app)

    # Core component registration
    _setup_logging(flask_app)
    _register_error_handlers(flask_app)
    _register_login_manager_loader(flask_app)

    # 6. Admin blueprints
    from .blueprints.admin_routes import admin_api_bp, admin_bp

    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(admin_api_bp)

    # 6.5 Tiles blueprint (global /tiles/* endpoints)
    from .routes.tiles import tiles_bp

    flask_app.register_blueprint(tiles_bp)

    # 7. Auto-discovered blueprints
    _register_blueprints(flask_app)

    # 8. Ensure tables exist in fallback scenarios
    # Skip calling _ensure_db_tables during Alembic migrations (ALEMBIC_RUNNING=1)
    if flask_app.testing or os.environ.get("ALEMBIC_RUNNING") != "1":
        with flask_app.app_context():
            _ensure_db_tables(flask_app)

    # 9. CLI commands
    try:
        from .cli import init_app as init_cli

        init_cli(flask_app)
    except Exception as exc:
        _logger.error("Failed to register CLI commands: %s", exc)

    from .cli_commands.sweep_endpoints import sweep_endpoints

    flask_app.cli.add_command(sweep_endpoints)

    # 10. Root health-check route for platform probes
    @flask_app.route("/health")
    def root_health_check():
        return {"status": "ok"}, 200

    return flask_app
