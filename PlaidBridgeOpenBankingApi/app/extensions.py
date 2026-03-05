# =============================================================================
# FILE: app/extensions.py
# DESCRIPTION: Core Flask Extensions & Service Bindings (hardened)
# =============================================================================

"""
Core Flask Extensions & Service Bindings (hardened).

This module provides module-level extension instances and a safe
init_extensions(app) entrypoint that initializes extensions in a
defensive way (avoids double-registration, provides testing-friendly
no-op limiter, and falls back to in-memory behavior when Redis is
unavailable).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

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

from .utils.redis_utils import get_redis_client

logger = logging.getLogger(__name__)

# --- SQLAlchemy naming convention ---
naming_convention: Dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=naming_convention)

# Typed SQLAlchemy instance used across the app
db: SQLAlchemy = SQLAlchemy(metadata=metadata)

# --- Core extensions (module-level instances) ---
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(async_mode="threading")
mail = Mail()
login_manager = LoginManager()
csrf = CSRFProtect()

# Backward-compatible module-level symbol for consumers that import it
redis_client: Optional[object] = None


# --- Safe No-op Limiter Stub ---
class _NoopLimiter:
    """
    A no-operation limiter that safely bypasses rate limiting.

    Used for testing environments or when rate limiting is disabled.
    Implements the same minimal interface as flask_limiter.Limiter so it can be
    used as a drop-in replacement.
    """

    def exempt(self, f):
        return f

    def limit(self, *a, **k):
        def decorator(f):
            return f

        return decorator

    def init_app(self, app):
        return None


limiter: Limiter | _NoopLimiter | None = None


# --- Helpers ---
def _already_registered(app: Any, key: str) -> bool:
    exts = getattr(app, "extensions", {})
    return isinstance(exts, dict) and (key in exts)


def _build_engine_options_from_env() -> Dict[str, Any]:
    try:
        return {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "280")),
            "pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "30")),
        }
    except Exception as exc:
        logger.warning("Failed building engine options, using defaults: %s", exc)
        return {"pool_pre_ping": True, "pool_recycle": 280}


def _init_limiter(app: Any, redis_enabled: bool) -> Limiter | _NoopLimiter:
    if app.config.get("TESTING"):
        app.logger.info("â±ï¸ Limiter disabled for testing (TESTING=True).")
        return _NoopLimiter()

    if not app.config.get("RATE_LIMIT_ENABLED", True):
        app.logger.info(
            "â±ï¸ Limiter disabled by configuration (RATE_LIMIT_ENABLED=False)."
        )
        return _NoopLimiter()

    limiter_storage_uri = os.getenv("REDIS_STORAGE_URI") if redis_enabled else None

    raw_config_limit = app.config.get("LIMITER_DEFAULTS")
    initial_limits: list[str] = []

    # Accept either list or tuple from configuration (use PEP 604 union type)
    if isinstance(raw_config_limit, list | tuple):
        initial_limits = list(raw_config_limit)
    elif isinstance(raw_config_limit, str) and raw_config_limit.strip():
        initial_limits = [limit_text.strip() for limit_text in raw_config_limit.split(",")]

    if not initial_limits:
        initial_limits = ["200 per day", "50 per hour"]

    fixed_limits: list[str] = []
    for limit_str in initial_limits:
        if limit_str.isdigit():
            fixed_limits.append(f"{limit_str} per minute")
        else:
            fixed_limits.append(limit_str)

    try:
        limiter_instance = Limiter(
            key_func=get_remote_address,
            storage_uri=limiter_storage_uri,
            enabled=redis_enabled,
            default_limits=fixed_limits,
            strategy=app.config.get("RATELIMIT_STRATEGY", "fixed-window"),
        )
        backend_type = "Redis" if redis_enabled else "in-memory"
        app.logger.info(
            "â±ï¸ Limiter created (%s backend, not yet initialized)", backend_type
        )
        return limiter_instance
    except Exception as exc:
        app.logger.error("âŒ Limiter creation failed: %s â€” falling back to no-op", exc)
        return _NoopLimiter()


# --- Extension initialization ---
def init_extensions(app: Any) -> None:
    """
    Initialize Flask extensions safely. This function is idempotent and
    defensive: it checks app.extensions to avoid double registration and
    provides sensible fallbacks when optional services (Redis) are not
    available.
    """
    global limiter, redis_client

    if not isinstance(getattr(app, "extensions", {}), dict):
        raise RuntimeError("app.extensions corrupted; cannot init safely.")

    engine_opts = _build_engine_options_from_env()
    if not app.config.get("SQLALCHEMY_ENGINE_OPTIONS"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts
        app.logger.debug("Set SQLALCHEMY_ENGINE_OPTIONS: %s", engine_opts)

    if not _already_registered(app, "migrate"):
        db.init_app(app)
        migrate.init_app(app, db)
        app.logger.info("ðŸ—„ï¸ SQLAlchemy and Migrate initialized.")

    if not _already_registered(app, "jwt"):
        jwt.init_app(app)
        app.logger.info("ðŸ” JWT initialized.")
        try:
            from app.models.revoked_token import RevokedToken
            from app.models.user import User

            @jwt.token_in_blocklist_loader
            def check_if_token_revoked(jwt_header, jwt_payload):
                jti = jwt_payload.get("jti")
                return RevokedToken.is_jti_blocklisted(jti)

            @jwt.user_lookup_loader
            def user_lookup_callback(_jwt_header, jwt_data):
                identity = jwt_data.get("sub")
                try:
                    return User.query.get(int(identity))
                except Exception:
                    return None

        except Exception as exc:
            app.logger.warning("âš ï¸ JWT handlers failed: %s", exc)

    if not _already_registered(app, "mail"):
        mail.init_app(app)
        app.logger.info("âœ‰ï¸ Mail initialized.")

    if not _already_registered(app, "socketio"):
        socketio.init_app(app)
        app.logger.info("ðŸ§µ SocketIO initialized.")

    if not _already_registered(app, "login"):
        login_manager.init_app(app)
        app.logger.info("ðŸ‘¤ LoginManager initialized.")

    if not _already_registered(app, "csrf"):
        csrf.init_app(app)
        app.logger.info("ðŸ›¡ï¸ CSRFProtect initialized.")

    redis_enabled = False
    try:
        rc = get_redis_client()
        app.redis_client = rc
        globals()["redis_client"] = rc
        if rc:
            redis_enabled = True
            redis_uri = os.getenv("REDIS_STORAGE_URI", "") or os.getenv("REDIS_URL", "")
            parsed = urlparse(redis_uri) if redis_uri else None
            safe_netloc = (parsed.hostname if parsed else None) or "unknown-host"
            scheme = (parsed.scheme if parsed else None) or "redis"
            logger.info(
                "ðŸ›°ï¸ Connected to Redis host: %s (scheme: %s)", safe_netloc, scheme
            )
        else:
            app.logger.warning(
                "âš ï¸ Redis unavailable â€” rate limiting and caching features will "
                "use in-memory backend."
            )
    except Exception as exc:
        app.redis_client = None
        globals()["redis_client"] = None
        redis_enabled = False
        app.logger.error(
            "âŒ Redis init failed: %s â€” rate limiter will use in-memory backend",
            exc,
        )

    try:
        limiter_instance = _init_limiter(app, redis_enabled)
        limiter_type = type(limiter_instance).__name__
        app.logger.info("â±ï¸ Limiter instance type: %s", limiter_type)

        if isinstance(limiter_instance, Limiter):
            limiter_instance.init_app(app)
            app.logger.info(
                "â±ï¸ Limiter registered with Flask (real Limiter instance)"
            )
        else:
            app.logger.info("â±ï¸ Limiter NOT registered with Flask (using _NoopLimiter)")

        limiter = limiter_instance
    except Exception as exc:
        app.logger.error("âŒ Unexpected error initializing limiter: %s", exc)
        limiter = _NoopLimiter()

