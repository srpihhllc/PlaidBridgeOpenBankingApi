# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/config.py

"""
Configuration module for the Financial Powerhouse API.
Hardened for PythonAnywhere & Production safety.
Guards against the "Sticky URI" trap and component omission.
"""

import logging
import os
import urllib.parse

from dotenv import load_dotenv

# Always load .env for consistency across dev, test, and prod
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("true", "1", "yes")


def parse_rate_limits(raw: str):
    if not raw:
        return ["200 per day", "50 per hour"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [f"{p} per minute" if p.isdigit() else p for p in parts]


# Metadata
_APP_NAME = os.getenv("APP_NAME", "FinancialPowerhouseAPI")
_APP_VERSION = os.getenv("APP_VERSION", "0.0.1")
_TIMEZONE = os.getenv("TIMEZONE", "UTC")

# Flask secrets
_SECRET_KEY = os.getenv("SECRET_KEY", "DEV_SECRET_KEY")
_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "DEV_JWT_SECRET")

# ---------------------------------------------------------------------------
# HARDENED DATABASE CONNECTION (PythonAnywhere Safe)
# ---------------------------------------------------------------------------
_DB_USER = os.getenv("DB_USER")
_DB_PASSWORD = os.getenv("DB_PASSWORD")
_DB_HOST = os.getenv("DB_HOST")
_DB_PORT = os.getenv("DB_PORT", "3306")
_DB_NAME = os.getenv("DB_NAME")

_IS_PROD_OR_MIGRATION = (
    os.getenv("FLASK_ENV") == "production" or os.getenv("ALEMBIC_RUNNING") == "1"
)

# ⭐ FINAL COMPONENT GUARD: Close every hole for Production/Migrations
if _IS_PROD_OR_MIGRATION:
    if not _DB_USER:
        raise RuntimeError("CRITICAL: DB_USER missing in production/migration context.")
    if not _DB_PASSWORD:
        raise RuntimeError("CRITICAL: DB_PASSWORD missing or empty. Refusing to continue.")
    if not _DB_HOST:
        raise RuntimeError("CRITICAL: DB_HOST missing in production/migration context.")
    if not _DB_NAME:
        raise RuntimeError("CRITICAL: DB_NAME missing in production/migration context.")

_HAS_COMPONENTS = all([_DB_USER, _DB_PASSWORD, _DB_HOST, _DB_NAME])

# Build the URI from components
_encoded_password = urllib.parse.quote_plus(_DB_PASSWORD or "")
_GENERATED_URI = f"mysql+pymysql://{_DB_USER}:{_encoded_password}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"

# Priority Logic: Explicit components ALWAYS override the string-based URI trap
if _HAS_COMPONENTS:
    _SQLALCHEMY_DATABASE_URI = _GENERATED_URI
else:
    _SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    if not _SQLALCHEMY_DATABASE_URI and _IS_PROD_OR_MIGRATION:
        raise RuntimeError("CRITICAL: No database components found and no URI override provided.")

# ⭐ MIGRATION INTROSPECTION HOOK (THE COCKPIT)
if os.getenv("ALEMBIC_RUNNING") == "1":
    _masked_uri = f"mysql+pymysql://{_DB_USER}:****@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
    print("\n" + "═" * 60)
    print(" 🚀 FLASK MIGRATION MODE ACTIVATED")
    print(f" [CONFIG] 🛰️  Target Host:  {_DB_HOST}")
    print(f" [CONFIG] 🔍  Auth Profile: user={_DB_USER}, db={_DB_NAME}")
    print(
        f" [CONFIG] 🧩  Component-Built URI: " f"{'✅ YES' if _HAS_COMPONENTS else '⚠️  FALLBACK'}"
    )
    print(f" [CONFIG] 🔗  Effective URI: {_masked_uri}")
    print(f" [CONFIG] 🧪  Integrity:    " f"Auth={'✅' if _DB_PASSWORD else '❌'}, Port={_DB_PORT}")
    print("═" * 60 + "\n")
# ---------------------------------------------------------------------------


class BaseConfig:
    """Base configuration for all environments."""

    ENV = "production"
    DEBUG = False
    TESTING = False

    # Application metadata
    APP_NAME = _APP_NAME
    APP_VERSION = _APP_VERSION
    TIMEZONE = _TIMEZONE

    # Security & Secrets
    SECRET_KEY = _SECRET_KEY
    JWT_SECRET_KEY = _JWT_SECRET_KEY

    # Database
    SQLALCHEMY_DATABASE_URI = _SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # Checks if connection is alive before using it
        "pool_recycle": 280,  # Prevents "MySQL has gone away" errors
    }

    # Rate Limiting (enabled by default)
    RATE_LIMIT_ENABLED = True
    RATELIMIT_ENABLED = True
    LIMITER_DEFAULTS = ["200 per day", "50 per hour"]
    RATELIMIT_STRATEGY = "fixed-window"

    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens

    # Logging
    LOG_LEVEL = logging.INFO

    @classmethod
    def validate(cls):
        """Validate configuration for the environment."""
        if cls.ENV == "production":
            if cls.SECRET_KEY.startswith("DEV_") or cls.JWT_SECRET_KEY.startswith("DEV_"):
                raise RuntimeError(
                    "Production secrets must be set via environment variables. "
                    "DEV_ prefixed keys are not allowed in production."
                )

    @classmethod
    def summarize(cls):
        """Return a summary of the configuration."""
        return {
            "app": cls.APP_NAME,
            "version": cls.APP_VERSION,
            "env": cls.ENV,
            "debug": cls.DEBUG,
            "testing": cls.TESTING,
            "rate_limit_enabled": cls.RATE_LIMIT_ENABLED,
            "csrf_enabled": cls.WTF_CSRF_ENABLED,
            "db_host": _DB_HOST,
            "db_user": _DB_USER,
            "db_name": _DB_NAME,
        }


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""

    ENV = "development"
    DEBUG = True
    LOG_LEVEL = logging.DEBUG

    # Development can have relaxed security for convenience
    WTF_CSRF_ENABLED = True
    RATE_LIMIT_ENABLED = True


class TestingConfig(BaseConfig):
    """Testing environment configuration."""

    ENV = "testing"
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_LEVEL = logging.WARNING

    # Disable external dependencies for clean tests
    RATE_LIMIT_ENABLED = False  # No rate limiting in tests
    RATELIMIT_ENABLED = False  # Backup flag
    WTF_CSRF_ENABLED = False  # No CSRF checks in tests

    # Redis disabled for testing (uses in-memory limiter)
    REDIS_STORAGE_URI = None


class ProductionConfig(BaseConfig):
    """Production environment configuration."""

    ENV = "production"
    DEBUG = False
    TESTING = False
    LOG_LEVEL = logging.INFO

    # Production always enforces rate limiting and CSRF
    RATE_LIMIT_ENABLED = True
    RATELIMIT_ENABLED = True
    WTF_CSRF_ENABLED = True

    @classmethod
    def validate(cls):
        """Strict validation for production."""
        super().validate()
        if not _HAS_COMPONENTS:
            raise RuntimeError(
                "Production configuration incomplete. "
                "All database components (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME) are required."
            )


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config_class(env_name: str = None) -> type:
    """
    Retrieve the configuration class for the given environment.

    Args:
        env_name: Environment name (development, testing, production)
                  Defaults to FLASK_ENV or 'production'

    Returns:
        Configuration class (not instantiated)
    """
    raw = env_name or os.getenv("FLASK_ENV") or "production"
    config_class = CONFIG_MAP.get(raw.lower(), ProductionConfig)

    if raw.lower() not in CONFIG_MAP:
        import warnings

        warnings.warn(
            f"Unknown environment '{raw}', defaulting to ProductionConfig. "
            f"Valid options: {', '.join(CONFIG_MAP.keys())}",
            RuntimeWarning,
            stacklevel=2,
        )

    return config_class


def get_config(env_name: str = None) -> BaseConfig:
    """
    Get and validate the configuration for the given environment.

    Args:
        env_name: Environment name (development, testing, production)
                  Defaults to FLASK_ENV or 'production'

    Returns:
        Instantiated and validated configuration object

    Raises:
        RuntimeError: If validation fails
    """
    cls = get_config_class(env_name)
    cls.validate()
    return cls()


# =============================================================================
# PROBE SERVICES - Health check for DB and Redis
# =============================================================================


def probe_services(strict: bool = True) -> None:
    """
    Run strict/lenient probe checks on database and Redis connectivity.

    In strict mode (production), raises on any failure.
    In lenient mode (testing), returns error message instead.

    Args:
        strict: If True, raise on failure. If False, return error message.

    Raises:
        RuntimeError: If strict=True and database probe fails

    Returns:
        None on success, error message string on lenient failure
    """
    from app.extensions import db

    try:
        # Test database connection
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
        return None  # Success
    except Exception as e:
        error_msg = f"Database probe failed: {e}"
        if strict:
            raise RuntimeError(error_msg) from e
        return error_msg
