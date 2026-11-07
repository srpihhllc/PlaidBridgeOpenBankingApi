# =============================================================================
# FILE: app/extensions.py
# DESCRIPTION: Core Flask Extensions & Service Bindings
# =============================================================================

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import urlparse

from flasgger import Swagger
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

from app.operator_cortex import OperatorCortex

from .utils.redis_utils import get_redis_client


# =============================================================================
# SQLAlchemy
# =============================================================================

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)
Base = declarative_base(metadata=metadata)

# Flask-SQLAlchemy exposes db.Model dynamically.
db: Any = SQLAlchemy(model_class=Base)


# =============================================================================
# Core extensions
# =============================================================================

migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(async_mode="threading")
mail = Mail()
login_manager = LoginManager()
csrf = CSRFProtect()
swagger = Swagger()

cortex = OperatorCortex()

# Backward-compatible module-level Redis reference.
# The authoritative client remains app.redis_client.
redis_client: object | None = None


# =============================================================================
# Helpers
# =============================================================================


def _is_sqlite_memory_database(app: Any) -> bool:
    """Return whether the configured database URL uses in-memory SQLite."""
    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not isinstance(database_uri, str) or not database_uri.strip():
        return False

    try:
        parsed_uri = urlparse(database_uri.strip())
    except ValueError:
        return False

    scheme = parsed_uri.scheme.lower()
    path = parsed_uri.path.lower()

    is_sqlite = scheme == "sqlite" or scheme.startswith("sqlite+")
    if not is_sqlite:
        return False

    # Covers URLs such as sqlite://, sqlite:///:memory:, and
    # sqlite+pysqlite:///:memory:.
    return path in {"", "/", "/:memory:"}


def _build_engine_options_from_env(app: Any) -> dict[str, Any]:
    """Build SQLAlchemy engine options from configuration and environment."""
    if _is_sqlite_memory_database(app):
        # Keep one shared in-memory database connection across app threads.
        # Pool sizing options are intentionally omitted for StaticPool.
        return {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }

    try:
        return {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "280")),
            "pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "30")),
        }
    except (TypeError, ValueError):
        app.logger.exception(
            "[DB] Failed building engine options; falling back to defaults"
        )
        return {
            "pool_pre_ping": True,
            "pool_recycle": 280,
        }


def _get_limiter_defaults(
    app: Any,
) -> list[str | Callable[[], str]]:
    """Read rate-limit defaults from Flask configuration."""
    configured_limits = app.config.get("LIMITER_DEFAULTS")

    if configured_limits is None:
        return ["200 per day", "50 per hour"]

    if isinstance(configured_limits, str):
        return [configured_limits]

    if isinstance(configured_limits, (list, tuple, set)):
        limits: list[str | Callable[[], str]] = []
        for value in configured_limits:
            if isinstance(value, str) or callable(value):
                limits.append(value)
            else:
                app.logger.warning(
                    "[LIMITER] Ignoring unsupported default limit value: %r",
                    value,
                )
        return limits

    app.logger.warning(
        "[LIMITER] Invalid LIMITER_DEFAULTS value; using built-in defaults"
    )
    return ["200 per day", "50 per hour"]


def _create_limiter(app: Any) -> Limiter:
    """Create a limiter owned exclusively by this Flask application."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=_get_limiter_defaults(app),
    )


def _get_limiter_storage_uri(app: Any, redis_enabled: bool) -> str:
    """Resolve the limiter storage URI without exposing credentials in logs."""
    if not redis_enabled:
        return "memory://"

    configured_uri = (
        os.getenv("REDIS_STORAGE_URI")
        or os.getenv("REDIS_URL")
        or app.config.get("RATELIMIT_STORAGE_URI")
    )

    if configured_uri:
        return str(configured_uri)

    redis_instance = getattr(app, "redis_client", None)

    if redis_instance is not None:
        try:
            connection_pool = redis_instance.connection_pool
            connection_kwargs = getattr(
                connection_pool,
                "connection_kwargs",
                {},
            )

            host = connection_kwargs.get("host", "localhost")
            port = connection_kwargs.get("port", 6379)
            db_number = connection_kwargs.get("db", 0)

            return f"redis://{host}:{port}/{db_number}"
        except Exception:
            app.logger.exception(
                "[LIMITER] Could not derive storage URI from Redis client"
            )

    return "redis://localhost:6379/0"


def _configure_limiter(
    app: Any,
    app_limiter: Limiter,
    redis_enabled: bool,
) -> None:
    """Configure and bind an app-specific limiter."""
    is_testing = bool(app.config.get("TESTING"))

    is_pytest = bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("PYTEST_RUNNING")
        or os.getenv("PYTEST_ADDOPTS")
    )

    rate_limit_enabled = bool(app.config.get("RATE_LIMIT_ENABLED", True))
    disabled_by_config = is_testing or is_pytest or not rate_limit_enabled

    if disabled_by_config:
        app_limiter.enabled = False
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"
        app.config.setdefault(
            "RATELIMIT_STRATEGY",
            app.config.get("RATELIMIT_STRATEGY", "fixed-window"),
        )

        try:
            app_limiter.init_app(app)
        except Exception:
            app.logger.exception(
                "[LIMITER] Disabled limiter initialization failed",
            )

        app.logger.info(
            "[LIMITER] Disabled "
            "(TESTING=%s, PYTEST=%s, RATE_LIMIT_ENABLED=%s)",
            is_testing,
            is_pytest,
            rate_limit_enabled,
        )
        return

    storage_uri = _get_limiter_storage_uri(
        app,
        redis_enabled=redis_enabled,
    )

    app.config["RATELIMIT_STORAGE_URI"] = storage_uri
    app.config.setdefault(
        "RATELIMIT_STRATEGY",
        app.config.get("RATELIMIT_STRATEGY", "fixed-window"),
    )

    app_limiter.enabled = True

    try:
        app_limiter.init_app(app)

        if not app_limiter.enabled:
            app.logger.info("[LIMITER] Disabled by RATELIMIT_ENABLED")
            return

        backend_type = type(app_limiter.storage).__name__
        app.logger.info(
            "[LIMITER] Initialized with %s backend",
            backend_type,
        )
    except Exception:
        app.logger.exception(
            "[LIMITER] Initialization failed; disabling limiter",
        )

        app_limiter.enabled = False

        # Keep the limiter app-owned; do not replace it with a module-level one.
        try:
            app_limiter.init_app(app)
        except Exception:
            app.logger.exception(
                "[LIMITER] Failed to attach disabled limiter",
            )


def _initialize_limiter(app: Any, redis_enabled: bool) -> Limiter:
    """Initialize or restore the limiter belonging to this Flask application."""
    extensions = app.extensions
    existing_limiter = extensions.get("limiter")

    if existing_limiter is not None:
        app.limiter = existing_limiter
        extensions["app_limiter_initialized"] = True

        app.logger.warning(
            "[LIMITER] Already initialized; restored app-specific limiter",
        )
        return cast(Limiter, existing_limiter)

    app_limiter = _create_limiter(app)

    try:
        _configure_limiter(
            app,
            app_limiter,
            redis_enabled=redis_enabled,
        )
    except Exception:
        app.logger.exception(
            "[LIMITER] Unexpected binding failure; disabling limiter",
        )
        app_limiter.enabled = False

    # The extension is authoritative; app.limiter is a compatibility alias.
    app.limiter = app_limiter
    extensions["limiter"] = app_limiter
    extensions["app_limiter_initialized"] = True

    return app_limiter


def _initialize_redis(app: Any) -> object | None:
    """Initialize Redis once for this Flask application."""
    global redis_client

    if app.extensions.get("app_redis_initialized"):
        return getattr(app, "redis_client", None)

    try:
        client = get_redis_client()

        app.redis_client = client
        redis_client = client

        if client:
            redis_uri = os.getenv("REDIS_STORAGE_URI", "") or os.getenv(
                "REDIS_URL", ""
            )

            parsed = urlparse(redis_uri) if redis_uri else None
            safe_host = (
                parsed.hostname
                if parsed and parsed.hostname
                else "unknown-host"
            )
            scheme = parsed.scheme if parsed and parsed.scheme else "redis"

            app.logger.info(
                "[REDIS] Connected to host: %s (scheme: %s)",
                safe_host,
                scheme,
            )

    except Exception:
        app.redis_client = None
        redis_client = None

        app.logger.exception("[REDIS] Redis initialization failed")

    app.extensions["app_redis_initialized"] = True
    return getattr(app, "redis_client", None)


def _emit_registry_telemetry(app: Any) -> None:
    """Emit registry telemetry once per Flask application."""
    if app.extensions.get("app_registry_telemetry_emitted"):
        return

    try:
        from app.services.registry import get_service_registry
        from app.telemetry.ttl_emit import emit_schema_trace

        discovered_services = get_service_registry()

        emit_schema_trace(
            domain="registry",
            event="service_registry",
            detail="discovery",
            value=f"services:{len(discovered_services)}",
            status="ok",
            ttl=1800,
            client=app.redis_client,
            meta={
                "services": [service.name for service in discovered_services],
            },
        )

    except Exception:
        app.logger.exception(
            "[TELEMETRY] Failed to emit service registry trace"
        )

    finally:
        app.extensions["app_registry_telemetry_emitted"] = True


# =============================================================================
# Extension initialization
# =============================================================================


def init_extensions(app: Any) -> None:
    """Initialize and bind core extensions to the Flask application."""
    if not isinstance(getattr(app, "extensions", None), dict):
        raise RuntimeError(
            "app.extensions corrupted; cannot initialize safely."
        )

    app.logger.debug(
        "[EXTENSIONS] Existing extension keys: %s",
        sorted(app.extensions.keys()),
    )

    # -------------------------------------------------------------------------
    # Database configuration
    # -------------------------------------------------------------------------

    database_uri = (
        app.config.get(
            "SQLALCHEMY_DATABASE_URI",
            "",
        )
        or ""
    )

    configured_engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS")

    if not configured_engine_options or not isinstance(
        configured_engine_options, dict
    ):
        engine_options = _build_engine_options_from_env(app)
    else:
        engine_options = dict(configured_engine_options)

    if database_uri.startswith("sqlite"):
        app.logger.info(
            "[DB] SQLite dialect detected; normalizing engine options"
        )

        for incompatible_key in (
            "pool_size",
            "max_overflow",
            "pool_timeout",
            "pool_recycle",
        ):
            engine_options.pop(incompatible_key, None)

        engine_options["poolclass"] = engine_options.get(
            "poolclass",
            StaticPool,
        )

        connect_args = engine_options.get("connect_args")

        if not isinstance(connect_args, dict):
            engine_options["connect_args"] = {
                "check_same_thread": False,
            }
        else:
            connect_args.setdefault(
                "check_same_thread",
                False,
            )

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = dict(engine_options)

    if not app.extensions.get("app_db_initialized"):
        db.init_app(app)
        migrate.init_app(app, db)

        app.extensions["app_db_initialized"] = True

        app.logger.info(
            "[DB] SQLAlchemy and Migrate initialized",
        )

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------

    if not app.extensions.get("app_jwt_initialized"):
        jwt.init_app(app)
        app.extensions["jwt"] = jwt  # Alias for legacy routes and test fixtures
        app.extensions["app_jwt_initialized"] = True

        app.logger.info(
            "[JWT] Initialized",
        )

        try:
            from .models.revoked_token import RevokedToken

            @jwt.token_in_blocklist_loader
            def check_if_token_revoked(jwt_header, jwt_payload):
                del jwt_header
                jti = jwt_payload.get("jti")
                return RevokedToken.is_jti_blocklisted(jti)

            @jwt.user_lookup_loader
            def user_lookup_callback(_jwt_header, jwt_data):
                from app.auth_handlers import _resolve_identity

                return _resolve_identity(jwt_data.get("sub"))

        except Exception:
            app.logger.exception("[JWT] Handlers setup failed")

    # -------------------------------------------------------------------------
    # Standard Flask extensions
    # -------------------------------------------------------------------------

    if not app.extensions.get("app_mail_initialized"):
        mail.init_app(app)
        app.extensions["app_mail_initialized"] = True

    if not app.extensions.get("app_socketio_initialized"):
        socketio.init_app(app)
        app.extensions["app_socketio_initialized"] = True

    if not app.extensions.get("app_login_initialized"):
        login_manager.init_app(app)
        app.extensions["app_login_initialized"] = True

    if not app.extensions.get("app_csrf_initialized"):
        csrf.init_app(app)
        app.extensions["app_csrf_initialized"] = True

    if not app.extensions.get("app_swagger_initialized"):
        swagger.init_app(app)
        app.extensions["app_swagger_initialized"] = True

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------

    redis_instance = _initialize_redis(app)

    # -------------------------------------------------------------------------
    # Rate limiter
    # -------------------------------------------------------------------------

    _initialize_limiter(
        app,
        redis_enabled=bool(redis_instance),
    )

    # -------------------------------------------------------------------------
    # Telemetry
    # -------------------------------------------------------------------------

    if redis_instance:
        _emit_registry_telemetry(app)

    app.logger.info(
        "[EXTENSIONS] Initialization complete",
    )