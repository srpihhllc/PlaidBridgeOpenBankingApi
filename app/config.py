# =============================================================================
# FILE: app/config.py
# DESCRIPTION: Application configuration, environment selection, and validation.
# =============================================================================

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"

if _DOTENV_PATH.is_file():
    load_dotenv(_DOTENV_PATH, override=False)

logger = logging.getLogger(__name__)


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def parse_rate_limits(raw: str | None) -> list[str]:
    if not raw:
        return ["200 per day", "50 per hour"]
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return [f"{part} per minute" if part.isdigit() else part for part in parts]


def _clean_env_string(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key, default)
    if value is None:
        return None
    return value.strip().strip("'\"")


def _ensure_redis_url(url: str | None) -> str | None:
    """Normalize managed Redis URLs that omit the default username."""
    if not url:
        return None
    if url.startswith("redis://:"):
        logger.warning("Redis URL omits username; inserting the default username.")
        return url.replace("redis://:", "redis://default:", 1)
    if url.startswith("rediss://:"):
        logger.warning("Redis TLS URL omits username; inserting the default username.")
        return url.replace("rediss://:", "rediss://default:", 1)
    return url


# Application metadata
_APP_NAME = os.getenv("APP_NAME", "PlaidBridgeOpenBankingApi")
_APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
_TIMEZONE = os.getenv("TIMEZONE", "UTC")

# Application secrets
_SECRET_KEY = _clean_env_string("SECRET_KEY", "DEV_SECRET_KEY")
_JWT_SECRET_KEY = _clean_env_string("JWT_SECRET_KEY", "DEV_JWT_SECRET")

# System operator settings
_SYSTEM_OPERATOR_ID = os.getenv("SYSTEM_OPERATOR_ID", "TERENCE_CORTEX_PRIME")
_SYSTEM_OPERATOR_ENABLED = as_bool(
    os.getenv("SYSTEM_OPERATOR_ENABLED", "True"),
    default=True,
)

# Polsia integration
_POLSIA_API_KEY = _clean_env_string("POLSIA_API_KEY", "")
_POLSIA_BASE_URL = _clean_env_string(
    "POLSIA_BASE_URL",
    "https://api.polsia.com/v1",
)
_POLSIA_WEBHOOK_SECRET = _clean_env_string(
    "POLSIA_WEBHOOK_SECRET",
    "default_secret_key",
)

# Database settings
_DB_USER = _clean_env_string("DB_USER")
_DB_PASSWORD = _clean_env_string("DB_PASSWORD")
_DB_HOST = _clean_env_string("DB_HOST")
_DB_PORT = _clean_env_string("DB_PORT", "3306")
_DB_NAME = _clean_env_string("DB_NAME")

if all([_DB_USER, _DB_PASSWORD, _DB_HOST, _DB_NAME]):
    _encoded_user = urllib.parse.quote_plus(_DB_USER or "")
    _encoded_password = urllib.parse.quote_plus(_DB_PASSWORD or "")
    _SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{_encoded_user}:{_encoded_password}"
        f"@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
    )
else:
    _SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///:memory:",
    )

# Redis settings. Either redis:// or rediss:// is accepted here.
_RAW_REDIS_URL = _clean_env_string("REDIS_URL") or _clean_env_string(
    "REDIS_STORAGE_URI"
)
_REDIS_URL = _ensure_redis_url(_RAW_REDIS_URL)
_REDIS_STORAGE_URI = _ensure_redis_url(
    _clean_env_string("REDIS_STORAGE_URI") or _REDIS_URL
)
_CELERY_BROKER_URL = _ensure_redis_url(
    _clean_env_string("CELERY_BROKER_URL")
)
_REDIS_SOCKET_TIMEOUT = int(os.getenv("REDIS_SOCKET_TIMEOUT", "15"))
_BLPOP_TIMEOUT = int(os.getenv("BLPOP_TIMEOUT", "5"))

# Plaid and webhook configuration. These are exposed as config attributes so
# application code can read them without accessing os.environ directly.
_PLAID_CLIENT_ID = _clean_env_string("PLAID_CLIENT_ID")
_PLAID_SECRET = _clean_env_string("PLAID_SECRET")
_PLAID_ENV = _clean_env_string("PLAID_ENV", "production")
_PLAID_ENCRYPTION_KEY = _clean_env_string("PLAID_ENCRYPTION_KEY")
_PLAID_ENCRYPTION_KEYS = _clean_env_string("PLAID_ENCRYPTION_KEYS")
_PLAID_PREVIOUS_KEYS = _clean_env_string("PLAID_PREVIOUS_KEYS")
_ACH_WEBHOOK_SECRET = _clean_env_string("ACH_WEBHOOK_SECRET")
_RECONCILE_WEBHOOK_SECRET = _clean_env_string("RECONCILE_WEBHOOK_SECRET")


class BaseConfig:
    ENV = "production"
    DEBUG = False
    TESTING = False
    LOG_LEVEL = logging.INFO
    DEBUG_UI = as_bool(os.getenv("DEBUG_UI"), default=False)

    APP_NAME = _APP_NAME
    APP_VERSION = _APP_VERSION
    TIMEZONE = _TIMEZONE

    SECRET_KEY = _SECRET_KEY
    JWT_SECRET_KEY = _JWT_SECRET_KEY

    SYSTEM_OPERATOR_ID = _SYSTEM_OPERATOR_ID
    SYSTEM_OPERATOR_ENABLED = _SYSTEM_OPERATOR_ENABLED

    POLSIA_API_KEY = _POLSIA_API_KEY
    POLSIA_BASE_URL = _POLSIA_BASE_URL
    POLSIA_WEBHOOK_SECRET = _POLSIA_WEBHOOK_SECRET

    PLAID_CLIENT_ID = _PLAID_CLIENT_ID
    PLAID_SECRET = _PLAID_SECRET
    PLAID_ENV = _PLAID_ENV
    PLAID_ENCRYPTION_KEY = _PLAID_ENCRYPTION_KEY
    PLAID_ENCRYPTION_KEYS = _PLAID_ENCRYPTION_KEYS
    PLAID_PREVIOUS_KEYS = _PLAID_PREVIOUS_KEYS
    ACH_WEBHOOK_SECRET = _ACH_WEBHOOK_SECRET
    RECONCILE_WEBHOOK_SECRET = _RECONCILE_WEBHOOK_SECRET

    REDIS_URL = _REDIS_URL
    REDIS_STORAGE_URI = _REDIS_STORAGE_URI
    REDIS_SOCKET_TIMEOUT = _REDIS_SOCKET_TIMEOUT
    CELERY_BROKER_URL = _CELERY_BROKER_URL
    BLPOP_TIMEOUT = _BLPOP_TIMEOUT

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
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

    RATELIMIT_DEFAULT = os.getenv(
        "RATELIMIT_DEFAULT",
        "200 per day;50 per hour",
    )

    @classmethod
    def validate(cls) -> None:
        if cls.ENV not in {"production", "staging"}:
            return

        db_user = _DB_USER or _clean_env_string("DB_USER")
        db_pass = _DB_PASSWORD or _clean_env_string("DB_PASSWORD")
        db_host = _DB_HOST or _clean_env_string("DB_HOST")
        db_name = _DB_NAME or _clean_env_string("DB_NAME")
        if not all([db_user, db_pass, db_host, db_name]):
            raise RuntimeError(
                f"{cls.ENV} relational database configuration is incomplete."
            )

        secret_key = _clean_env_string("SECRET_KEY") or cls.SECRET_KEY
        jwt_secret = _clean_env_string("JWT_SECRET_KEY") or cls.JWT_SECRET_KEY
        if (
            not secret_key
            or secret_key.startswith("DEV_")
            or not jwt_secret
            or jwt_secret.startswith("DEV_")
        ):
            raise RuntimeError(
                f"{cls.ENV} requires non-development SECRET_KEY "
                "and JWT_SECRET_KEY values."
            )

        for label, url in (
            ("REDIS_URL", cls.REDIS_URL),
            ("REDIS_STORAGE_URI", cls.REDIS_STORAGE_URI),
            ("CELERY_BROKER_URL", cls.CELERY_BROKER_URL),
        ):
            if url and not url.startswith(("redis://", "rediss://")):
                raise RuntimeError(
                    f"{label} must begin with redis:// or rediss://."
                )

        if cls.REDIS_SOCKET_TIMEOUT <= cls.BLPOP_TIMEOUT:
            raise RuntimeError(
                "REDIS_SOCKET_TIMEOUT must exceed BLPOP_TIMEOUT."
            )

        from app.services.pii_manager import validate_pii_keys
        from app.utils.plaid_crypto import validate_plaid_keys

        validate_plaid_keys()
        validate_pii_keys()

    @classmethod
    def summarize(cls) -> dict:
        return {
            "app": cls.APP_NAME,
            "version": cls.APP_VERSION,
            "env": cls.ENV,
            "db_host": _DB_HOST,
            "db_name": _DB_NAME,
            "debug_ui": cls.DEBUG_UI,
            "system_operator_enabled": cls.SYSTEM_OPERATOR_ENABLED,
        }


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    REDIS_URL = _REDIS_URL or "redis://localhost:6379/0"
    REDIS_STORAGE_URI = _REDIS_STORAGE_URI or "redis://localhost:6379/0"
    CELERY_BROKER_URL = _CELERY_BROKER_URL or "redis://localhost:6379/0"


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-sentinel-key"
    JWT_SECRET_KEY = "test-jwt-sentinel-key"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False

    SYSTEM_OPERATOR_ID = "TERENCE_CORTEX_PRIME"
    SYSTEM_OPERATOR_ENABLED = True

    REDIS_URL = _REDIS_URL or "redis://localhost:6379/0"
    REDIS_STORAGE_URI = _REDIS_STORAGE_URI or "redis://localhost:6379/0"
    CELERY_BROKER_URL = _CELERY_BROKER_URL or "redis://localhost:6379/0"
    SERVER_NAME = os.getenv("TEST_SERVER_NAME", "localhost")
    PREFERRED_URL_SCHEME = os.getenv("TEST_PREFERRED_URL_SCHEME", "http")


class StagingConfig(BaseConfig):
    ENV = "staging"
    DEBUG = False
    LOG_LEVEL = logging.INFO


class ProductionConfig(BaseConfig):
    ENV = "production"
    DEBUG = False
    LOG_LEVEL = logging.INFO


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
    "staging": StagingConfig,
}


def get_config_class(env_name: str | None = None):
    if isinstance(env_name, str) and env_name.strip().lower() == "testing":
        return TestingConfig

    indicators = {
        (os.getenv("ENV_NAME") or "").strip().lower(),
        (os.getenv("FLASK_ENV") or "").strip().lower(),
    }

    # Production/staging indicators override FLASK_CONFIG and non-testing selections.
    if indicators & {"production", "prod"}:
        return ProductionConfig
    if "staging" in indicators:
        return StagingConfig

    raw = (
        env_name
        or os.getenv("FLASK_CONFIG")
        or os.getenv("ENV_NAME")
        or os.getenv("FLASK_ENV")
        or "production"
    ).strip().lower()

    return CONFIG_MAP.get(raw, ProductionConfig)


def get_config(env_name: str | None = None):
    config_class = get_config_class(env_name)
    config_class.validate()
    return config_class()


def probe_services(strict: bool = True) -> str | None:
    from app.extensions import db

    try:
        db.session.execute(db.text("SELECT 1"))
        db.session.commit()
    except Exception as exc:
        if strict:
            raise RuntimeError(
                f"Database infrastructure verification probe failed: {exc}"
            ) from exc
        return str(exc)
    return None


class TestConfig(TestingConfig):
    """Legacy alias retained for backwards compatibility."""