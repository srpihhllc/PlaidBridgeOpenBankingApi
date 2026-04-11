# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/config.py

# Minimal/compatible configuration module derived from tests (safe for local testing).
# DO NOT commit secrets. Use environment variables in production and CI.

import logging
import os
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

# Always load .env for local consistency (tests expect this)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_dotenv_path = os.path.join(_PROJECT_ROOT, ".env")
if Path(_dotenv_path).exists():
    load_dotenv(_dotenv_path, override=False)

logger = logging.getLogger(__name__)


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("true", "1", "yes")


def parse_rate_limits(raw: str | None):
    if not raw:
        return ["200 per day", "50 per hour"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [f"{p} per minute" if p.isdigit() else p for p in parts]


def _ensure_redis_url(url: str | None) -> str | None:
    """
    Normalize Redis URL if it uses the pattern redis://:PASSWORD@host:port (no username).
    Some hosted Redis providers (e.g. Redis Labs with ACLs) require a username such as "default".
    If the URL starts with redis://: we replace that prefix with redis://default: so clients that
    expect a username:password form will work.

    NOTE: This is a best-effort convenience for development/testing. In production, set a correct
    REDIS_URL explicitly in the environment (e.g. redis://default:password@host:port/0).
    """
    if not url:
        return None
    # quick detect for "redis://:password@host" (no username)
    if url.startswith("redis://:"):
        logger.warning("Redis URL appears to have no username; inserting 'default' username for compatibility.")
        return url.replace("redis://:", "redis://default:", 1)
    return url


# Metadata
_APP_NAME = os.getenv("APP_NAME", "FinancialPowerhouseAPI")
_APP_VERSION = os.getenv("APP_VERSION", "0.0.1")
_TIMEZONE = os.getenv("TIMEZONE", "UTC")

# Flask secrets (use env vars; these defaults are safe for tests only)
_SECRET_KEY = os.getenv("SECRET_KEY", "DEV_SECRET_KEY")
_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "DEV_JWT_SECRET")

# Database components
_DB_USER = os.getenv("DB_USER")
_DB_PASSWORD = os.getenv("DB_PASSWORD")
_DB_HOST = os.getenv("DB_HOST")
_DB_PORT = os.getenv("DB_PORT", "3306")
_DB_NAME = os.getenv("DB_NAME")

_IS_PROD_OR_MIGRATION = (
    os.getenv("FLASK_ENV") == "production" or os.getenv("ALEMBIC_RUNNING") == "1"
)

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

_encoded_password = urllib.parse.quote_plus(_DB_PASSWORD or "")
_GENERATED_URI = f"mysql+pymysql://{_DB_USER}:{_encoded_password}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"

if _HAS_COMPONENTS:
    _SQLALCHEMY_DATABASE_URI = _GENERATED_URI
else:
    _SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    if not _SQLALCHEMY_DATABASE_URI and _IS_PROD_OR_MIGRATION:
        raise RuntimeError("CRITICAL: No database components found and no URI override provided.")


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

    # Rate limit defaults (can be overridden by env)
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per day;50 per hour")

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
    # Use local redis by default in development if not provided
    REDIS_URL = _ensure_redis_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"
    # Disable Flask-WTF CSRF checks in tests so test clients can POST forms without tokens
    WTF_CSRF_ENABLED = False
    # Disable rate limiting in tests by default
    RATELIMIT_ENABLED = False
    SENDGRID_API_KEY = None
    REFLECTORAI_API_KEY = None
    REFLECTORAI_API_ENDPOINT = None
    # For tests, default to localhost Redis (or pick up REDIS_URL from env)
    REDIS_URL = _ensure_redis_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Make url_for() work outside request contexts during tests:
    # When building URLs outside an active request Flask requires SERVER_NAME.
    # PREFERRED_URL_SCHEME is set so generated external URLs use http in tests.
    SERVER_NAME = os.getenv("TEST_SERVER_NAME", "localhost")
    PREFERRED_URL_SCHEME = os.getenv("TEST_PREFERRED_URL_SCHEME", "http")


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False
    LOG_LEVEL = logging.INFO
    # In production, require REDIS_URL to be explicitly provided via env; do not invent credentials.
    REDIS_URL = _ensure_redis_url(os.getenv("REDIS_URL", None))


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config_class(env_name: str | None = None):
    raw = env_name or os.getenv("FLASK_ENV") or "production"
    return CONFIG_MAP.get(raw.lower(), ProductionConfig)


def get_config(env_name: str | None = None):
    cls = get_config_class(env_name)
    cls.validate()
    return cls()


def probe_services(strict: bool = True) -> None:
    from app.extensions import db

    try:
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
    except Exception as e:
        if strict:
            raise RuntimeError(f"Database probe failed: {e}") from e
        return str(e)
    return None

class TestConfig(TestingConfig):
    """Backwards-compatible alias used by older tests."""
    pass