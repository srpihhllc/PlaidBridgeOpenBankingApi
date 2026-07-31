# =============================================================================
# FILE: /home/srpihhllc/PlaidBridgeOpenBankingApi/app/config.py
# DESCRIPTION: Defensively-engineered configuration parser layer.
#              Safeguards connection strings from malformed env inputs.
# =============================================================================

import logging
import os
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# Enforce explicit .env ingestion across execution paradigms
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_dotenv_path = os.path.join(_PROJECT_ROOT, ".env")
if Path(_dotenv_path).exists():
    load_dotenv(_dotenv_path, override=False)

logger = logging.getLogger(__name__)


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("true", "1", "yes", "on")


def parse_rate_limits(raw: str | None) -> list[str]:
    if not raw:
        return ["200 per day", "50 per hour"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [f"{p} per minute" if p.isdigit() else p for p in parts]


def _ensure_redis_url(url: str | None) -> str | None:
    """Normalizes missing usernames in managed Redis strings to default."""
    if not url:
        return None
    if url.startswith("redis://:"):
        logger.warning("Redis engine string missing user context; applying 'default' fallback schema.")
        return url.replace("redis://:", "redis://default:", 1)
    return url


# Clean string values extracted from environments to eliminate accidental literal outer quotes
def _clean_env_string(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    if val:
        return val.strip("'\"")
    return val


# Metadata Ingestion
_APP_NAME = os.getenv("APP_NAME", "PlaidBridgeOpenBankingApi")
_APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
_TIMEZONE = os.getenv("TIMEZONE", "UTC")

# Fallback Cryptographic Keys
_SECRET_KEY = os.getenv("SECRET_KEY", "DEV_SECRET_KEY")
_JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "DEV_JWT_SECRET")

# Relational Database Context Sanitation
_DB_USER = _clean_env_string("DB_USER")
_DB_PASSWORD = _clean_env_string("DB_PASSWORD")
_DB_HOST = _clean_env_string("DB_HOST")
_DB_PORT = _clean_env_string("DB_PORT", "3306")
_DB_NAME = _clean_env_string("DB_NAME")

# Unified Dynamic Unified Cache Resolution
_RAW_REDIS_TARGET = os.getenv("REDIS_URL") or os.getenv("REDIS_STORAGE_URI")

# System Stage Verification Evaluator
_IS_PROD_OR_MIGRATION = (
    str(os.getenv("FLASK_ENV")).lower() == "production" or 
    str(os.getenv("ENV_NAME")).lower() == "production" or 
    os.getenv("ALEMBIC_RUNNING") == "1"
)

if _IS_PROD_OR_MIGRATION:
    if not all([_DB_USER, _DB_PASSWORD, _DB_HOST, _DB_NAME]):
        raise RuntimeError("CRITICAL: Production relational configuration matrix is incomplete.")

# Secure Connection Construction using percent-encoded parameterization
if all([_DB_USER, _DB_PASSWORD, _DB_HOST, _DB_NAME]):
    _encoded_password = urllib.parse.quote_plus(_DB_PASSWORD or "")
    _SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{_DB_USER}:{_encoded_password}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
else:
    _SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")


class BaseConfig:
    ENV = "production"
    DEBUG = False
    TESTING = False
    DEBUG_UI = as_bool(os.getenv("DEBUG_UI"), default=False)

    APP_NAME = _APP_NAME
    APP_VERSION = _APP_VERSION
    TIMEZONE = _TIMEZONE

    SECRET_KEY = _SECRET_KEY
    JWT_SECRET_KEY = _JWT_SECRET_KEY

    # SMTP Mail Handlers
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = as_bool(os.getenv("MAIL_USE_TLS", "True"), default=True)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    SQLALCHEMY_DATABASE_URI = _SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per day;50 per hour")

    @classmethod
    def validate(cls):
        if cls.ENV == "production":
            if cls.SECRET_KEY.startswith("DEV_") or cls.JWT_SECRET_KEY.startswith("DEV_"):
                raise RuntimeError("Production environments must employ high-entropy token secrets.")

    @classmethod
    def summarize(cls) -> dict:
        return {
            "app": cls.APP_NAME,
            "version": cls.APP_VERSION,
            "env": cls.ENV,
            "db_host": _DB_HOST,
            "db_name": _DB_NAME,
            "debug_ui": cls.DEBUG_UI,
        }


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    REDIS_URL = _ensure_redis_url(_RAW_REDIS_TARGET or "redis://localhost:6379/0")


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-sentinel-key"
    JWT_SECRET_KEY = "test-jwt-sentinel-key"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    REDIS_URL = _ensure_redis_url(_RAW_REDIS_TARGET or "redis://localhost:6379/0")
    SERVER_NAME = os.getenv("TEST_SERVER_NAME", "localhost")
    PREFERRED_URL_SCHEME = os.getenv("TEST_PREFERRED_URL_SCHEME", "http")


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False
    LOG_LEVEL = logging.INFO
    REDIS_URL = _ensure_redis_url(_RAW_REDIS_TARGET)


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config_class(env_name: str | None = None):
    raw = env_name or os.getenv("ENV_NAME") or os.getenv("FLASK_ENV") or "production"
    return CONFIG_MAP.get(raw.lower(), ProductionConfig)


def get_config(env_name: str | None = None):
    cls = get_config_class(env_name)
    cls.validate()
    return cls()


def probe_services(strict: bool = True) -> str | None:
    from app.extensions import db
    try:
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
    except Exception as e:
        if strict:
            raise RuntimeError(f"Database infrastructure verification probe failed: {e}") from e
        return str(e)
    return None


class TestConfig(TestingConfig):
    """Legacy alias matching back-compatibility test cases."""
    pass