import logging

import pytest
from flask import Flask
from limits.storage import MemoryStorage, RedisStorage
from redis.connection import Connection

from app.extensions import _configure_limiter, _create_limiter


@pytest.fixture
def clear_trace_events_between_tests():
    """These standalone Flask apps do not use the project database."""


@pytest.fixture
def mock_global_ttl_emit():
    """These standalone Flask apps do not initialize telemetry."""


@pytest.fixture
def production_limiter_environment(monkeypatch):
    def clear_environment():
        for name in (
            "PYTEST_CURRENT_TEST",
            "PYTEST_RUNNING",
            "PYTEST_ADDOPTS",
            "REDIS_STORAGE_URI",
            "REDIS_URL",
        ):
            monkeypatch.delenv(name, raising=False)

    return clear_environment


@pytest.mark.parametrize(
    ("redis_enabled", "storage_class"),
    [(False, MemoryStorage), (True, RedisStorage)],
)
def test_configured_backend_matches_actual_storage(
    production_limiter_environment, monkeypatch, caplog, redis_enabled, storage_class
):
    production_limiter_environment()

    def forbid_network(*args, **kwargs):
        raise AssertionError("Redis must not connect during initialization")

    monkeypatch.setattr(Connection, "connect", forbid_network)
    monkeypatch.setenv("REDIS_STORAGE_URI", "redis://localhost:6379/0")
    app = Flask(__name__)
    app.config.update(TESTING=False, RATE_LIMIT_ENABLED=True)
    limiter = _create_limiter(app)

    with caplog.at_level(logging.INFO, logger=app.logger.name):
        _configure_limiter(app, limiter, redis_enabled=redis_enabled)

    assert limiter.enabled
    assert isinstance(limiter.storage, storage_class)
    assert f"Initialized with {storage_class.__name__} backend" in caplog.text


def test_memory_backend_enforces_default_limit(production_limiter_environment):
    production_limiter_environment()
    app = Flask(__name__)
    app.config.update(
        TESTING=False, RATE_LIMIT_ENABLED=True, LIMITER_DEFAULTS=["2 per minute"]
    )
    limiter = _create_limiter(app)
    _configure_limiter(app, limiter, redis_enabled=False)

    @app.get("/limited")
    def limited():
        return "ok"

    client = app.test_client()
    assert [client.get("/limited").status_code for _ in range(3)] == [200, 200, 429]


def test_library_disabled_limiter_does_not_log_backend_failure(
    production_limiter_environment, caplog
):
    production_limiter_environment()
    app = Flask(__name__)
    app.config.update(TESTING=False, RATE_LIMIT_ENABLED=True, RATELIMIT_ENABLED=False)
    limiter = _create_limiter(app)

    with caplog.at_level(logging.INFO, logger=app.logger.name):
        _configure_limiter(app, limiter, redis_enabled=True)

    assert not limiter.enabled
    assert "[LIMITER] Disabled by RATELIMIT_ENABLED" in caplog.text
    assert "[LIMITER] Initialization failed" not in caplog.text


@pytest.mark.parametrize(
    ("testing", "rate_limit_enabled"),
    [(True, True), (False, False)],
)
def test_disabled_limiter_does_not_initialize_redis(
    production_limiter_environment, testing, rate_limit_enabled
):
    production_limiter_environment()
    app = Flask(__name__)
    app.config.update(TESTING=testing, RATE_LIMIT_ENABLED=rate_limit_enabled)
    limiter = _create_limiter(app)

    _configure_limiter(app, limiter, redis_enabled=True)

    assert not limiter.enabled
    assert app.config["RATELIMIT_STORAGE_URI"] == "memory://"
