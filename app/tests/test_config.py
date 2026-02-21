# =============================================================================
# FILE: app/tests/test_config.py
# DESCRIPTION: Configuration sanity checks for critical environment keys.
# =============================================================================

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
    print(f" [CONFIG] 🧪  Integrity:    Auth={'✅' if _DB_PASSWORD else '❌'}, " f"Port={_DB_PORT}")
    print("═" * 60 + "\n")
# ---------------------------------------------------------------------------


class BaseConfig:
    ENV = "production"
    DEBUG = False
    TESTING = False

    APP_NAME = _APP_NAME
    APP_VERSION = _APP_VERSION
    TIMEZONE = _TIMEZONE

    SECRET_KEY = _SECRET_KEY
    JWT_SECRET_KEY = _JWT_SECRET_KEY

    SQLALCHEMY_DATABASE_URI = _SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    @classmethod
    def validate(cls):
        if cls.ENV == "production":
            if cls.SECRET_KEY.startswith("DEV_") or cls.JWT_SECRET_KEY.startswith("DEV_"):
                raise RuntimeError("Production secrets must be set via environment variables.")

    @classmethod
    def summarize(cls):
        return {
            "app": cls.APP_NAME,
            "version": cls.APP_VERSION,
            "env": cls.ENV,
            "db_host": _DB_HOST,
            "db_user": _DB_USER,
            "db_name": _DB_NAME,
        }


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


# ---------------------------------------------------------------------------
# ⭐ UPDATED TESTING CONFIG (FULLY ALIGNED WITH TEST SUITE)
# ---------------------------------------------------------------------------
class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True

    # SQLite in-memory
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Required by test suite
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"

    # Disable rate limiting
    RATELIMIT_ENABLED = False

    # Disable external APIs
    SENDGRID_API_KEY = None
    REFLECTORAI_API_KEY = None
    REFLECTORAI_API_ENDPOINT = None

    # Redis stub for tests
    REDIS_URL = "redis://localhost:6379/0"


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False
    LOG_LEVEL = logging.INFO


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config_class(env_name: str = None):
    raw = env_name or os.getenv("FLASK_ENV") or "production"
    return CONFIG_MAP.get(raw.lower(), ProductionConfig)


def get_config(env_name: str = None):
    cls = get_config_class(env_name)
    cls.validate()
    return cls()


# =============================================================================
# PROBE SERVICES - Health check for DB and Redis
# =============================================================================


def probe_services(strict: bool = True) -> None:
    """
    Runs strict/lenient probe checks on database and Redis connectivity.
    Returns None on success; raises if strict=True and checks fail.
    """
    from app.extensions import db

    try:
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
    except Exception as e:
        if strict:
            raise RuntimeError(f"Database probe failed: {e}") from e
        return str(e)

    return None
