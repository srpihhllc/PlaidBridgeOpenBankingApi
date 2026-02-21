# =============================================================================
# FILE: app/extensions.py
# DESCRIPTION: Core Flask Extensions & Service Bindings (hardened)
# =============================================================================

from __future__ import annotations

import logging
import os
from typing import Any
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

from app.utils.redis_utils import get_redis_client

logger = logging.getLogger(__name__)

# --- SQLAlchemy naming convention ---
naming_convention = {
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
redis_client: object | None = None


# --- Safe No-op Limiter Stub ---
class _NoopLimiter:
    """
    A no-operation limiter that safely bypasses rate limiting.

    Used for testing environments or when rate limiting is disabled.
    Implements the same minimal interface as flask_limiter.Limiter so it can be
    used as a drop-in replacement.
    """

    def exempt(self, f):
        """Return function unchanged (no exemption needed)."""
        return f

    def limit(self, *a, **k):
        """Return a pass-through decorator that doesn't limit anything."""

        def decorator(f):
            return f

        return decorator

    def init_app(self, app):
        """No-op init_app for compatibility."""
        return None


limiter: Limiter | _NoopLimiter | None = None


# --- Helpers ---
def _already_registered(app: Any, key: str) -> bool:
    """Check if an extension has already been registered with the app."""
    exts = getattr(app, "extensions", {})
    return isinstance(exts, dict) and (key in exts)


def _build_engine_options_from_env() -> dict:
    """Build SQLAlchemy engine options from environment variables."""
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
    """
    Initialize the rate limiter based on app configuration.

    CRITICAL: This function returns either a _NoopLimiter or a Limiter.
    It does NOT call init_app() - that happens in init_extensions().

    Args:
        app: Flask application instance
        redis_enabled: Whether Redis is available for the limiter backend

    Returns:
        Limiter | _NoopLimiter: A real Limiter instance or a no-op fallback.
    """
    # ⭐ CRITICAL: Testing mode is HIGHEST PRIORITY - check first, return immediately
    if app.config.get("TESTING"):
        app.logger.info("⏱️ Limiter disabled for testing (TESTING=True).")
        return _NoopLimiter()

    # Rate limiting disabled globally
    if not app.config.get("RATE_LIMIT_ENABLED", True):
        app.logger.info("⏱️ Limiter disabled by configuration (RATE_LIMIT_ENABLED=False).")
        return _NoopLimiter()

    # Extract limiter storage URI
    limiter_storage_uri = os.getenv("REDIS_STORAGE_URI") if redis_enabled else None

    # Parse default limits from config
    raw_config_limit = app.config.get("LIMITER_DEFAULTS")
    initial_limits: list[str] = []

    if isinstance(raw_config_limit, (list, tuple)):
        initial_limits = list(raw_config_limit)
    elif isinstance(raw_config_limit, str) and raw_config_limit.strip():
        initial_limits = [limit_text.strip() for limit_text in raw_config_limit.split(",")]

    # Fallback to sensible defaults
    if not initial_limits:
        initial_limits = ["200 per day", "50 per hour"]

    # Normalize limits (convert bare numbers to "N per minute")
    fixed_limits: list[str] = []
    for limit_str in initial_limits:
        if limit_str.isdigit():
            fixed_limits.append(f"{limit_str} per minute")
        else:
            fixed_limits.append(limit_str)

    try:
        # Create limiter instance but DO NOT call init_app() here
        limiter_instance = Limiter(
            key_func=get_remote_address,
            storage_uri=limiter_storage_uri,
            enabled=redis_enabled,
            default_limits=fixed_limits,
            strategy=app.config.get("RATELIMIT_STRATEGY", "fixed-window"),
        )
        backend_type = "Redis" if redis_enabled else "in-memory"
        app.logger.info(f"⏱️ Limiter created ({backend_type} backend, not yet initialized)")
        return limiter_instance
    except Exception as e:
        app.logger.error(f"❌ Limiter creation failed: {e} — falling back to no-op")
        return _NoopLimiter()


# --- Extension initialization ---
def init_extensions(app: Any) -> None:
    """
    Initialize and bind core extensions to the Flask app.

    This function:
    - Validates app.extensions is a proper dict
    - Configures SQLAlchemy engine options from environment
    - Initializes db, migrate, jwt, mail, socketio, login_manager, csrf
    - Connects to Redis (if available) and configures dependent features
    - Initializes rate limiter (with graceful fallback on errors)
    - Sets app.redis_client and module-level redis_client for backwards compatibility

    Raises:
        RuntimeError: If app.extensions is corrupted or not a dict

    Note:
        Extensions are only initialized once. Calling this function multiple times
        is safe due to the _already_registered() guard checks.
    """
    global limiter, redis_client

    if not isinstance(getattr(app, "extensions", {}), dict):
        raise RuntimeError("app.extensions corrupted; cannot init safely.")

    # SQLAlchemy engine options
    engine_opts = _build_engine_options_from_env()
    if not app.config.get("SQLALCHEMY_ENGINE_OPTIONS"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts
        app.logger.debug("Set SQLALCHEMY_ENGINE_OPTIONS: %s", engine_opts)

    # DB & Migrations
    if not _already_registered(app, "migrate"):
        db.init_app(app)
        migrate.init_app(app, db)
        app.logger.info("🗄️ SQLAlchemy and Migrate initialized.")

    # JWT
    if not _already_registered(app, "jwt"):
        jwt.init_app(app)
        app.logger.info("🔐 JWT initialized.")
        try:
            from app.models.revoked_token import RevokedToken
            from app.models.user import User

            @jwt.token_in_blocklist_loader
            def check_if_token_revoked(jwt_header, jwt_payload):
                """Check if the JWT's JTI is in the revocation blocklist."""
                jti = jwt_payload.get("jti")
                return RevokedToken.is_jti_blocklisted(jti)

            @jwt.user_lookup_loader
            def user_lookup_callback(_jwt_header, jwt_data):
                """
                Resolve the user from the JWT 'sub' claim.

                Must stay in sync with the identity loader in app/__init__.py,
                which guarantees that 'sub' is always the integer user ID.
                """
                identity = jwt_data.get("sub")
                try:
                    return User.query.get(int(identity))
                except Exception:
                    return None

        except Exception as e:
            app.logger.warning(f"⚠️ JWT handlers failed: {e}")

    # Mail
    if not _already_registered(app, "mail"):
        mail.init_app(app)
        app.logger.info("✉️ Mail initialized.")

    # SocketIO
    if not _already_registered(app, "socketio"):
        socketio.init_app(app)
        app.logger.info("🧵 SocketIO initialized.")

    # LoginManager
    if not _already_registered(app, "login"):
        login_manager.init_app(app)
        app.logger.info("👤 LoginManager initialized.")

    # CSRFProtect
    if not _already_registered(app, "csrf"):
        csrf.init_app(app)
        app.logger.info("🛡️ CSRFProtect initialized.")

    # Redis client (MUST come before limiter, as limiter depends on redis_client)
    redis_enabled = False
    try:
        rc = get_redis_client()
        app.redis_client = rc
        # Update module-level symbol for import-time consumers
        globals()["redis_client"] = rc
        if rc:
            redis_enabled = True
            redis_uri = os.getenv("REDIS_STORAGE_URI", "") or os.getenv("REDIS_URL", "")
            parsed = urlparse(redis_uri) if redis_uri else None
            safe_netloc = (parsed.hostname if parsed else None) or "unknown-host"
            scheme = (parsed.scheme if parsed else None) or "redis"
            logger.info(f"🛰️ Connected to Redis host: {safe_netloc} (scheme: {scheme})")
        else:
            app.logger.warning(
                "⚠️ Redis unavailable — rate limiting and caching features will use "
                "in-memory backend."
            )
    except Exception as e:
        app.redis_client = None
        globals()["redis_client"] = None
        redis_enabled = False
        app.logger.error(f"❌ Redis init failed: {e} — rate limiter will use in-memory backend")

    # Limiter (AFTER Redis initialization, since it depends on redis_client)
    # CRITICAL: Only call init_app() if we have a real Limiter, not a _NoopLimiter
    try:
        limiter_instance = _init_limiter(app, redis_enabled)

        # Debug: Log the limiter type
        limiter_type = type(limiter_instance).__name__
        app.logger.info(f"⏱️ Limiter instance type: {limiter_type}")

        # Only initialize with Flask if it's a real Limiter instance
        if isinstance(limiter_instance, Limiter):
            limiter_instance.init_app(app)
            app.logger.info("⏱️ Limiter registered with Flask (real Limiter instance)")
        else:
            app.logger.info("⏱️ Limiter NOT registered with Flask (using _NoopLimiter)")

        limiter = limiter_instance
    except Exception as e:
        app.logger.error(f"❌ Unexpected error initializing limiter: {e}")
        limiter = _NoopLimiter()
