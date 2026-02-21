# =============================================================================
# FILE: app/tests/redis_utils.py
# DESCRIPTION: Tests for cockpit‑grade Redis client factory in app/utils/redis_utils.py
# =============================================================================

import os

import pytest
from flask import Flask

from app.utils import redis_utils


@pytest.fixture
def app_context():
    """Provides a Flask application context for testing."""
    app = Flask(__name__)
    app.config["REDIS_STORAGE_URI"] = "redis://localhost:6379"
    app.config["REDIS_CONNECT_TIMEOUT"] = 1
    app.config["REDIS_SOCKET_TIMEOUT"] = 2
    ctx = app.app_context()
    ctx.push()
    yield app
    ctx.pop()


class MockRedisClient:
    """A minimal mock for the Redis client."""

    def ping(self):
        return True

    def setex(self, *a, **k):
        pass

    def get(self, *a, **k):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_get_redis_client_success(monkeypatch, app_context):
    """get_redis_client returns a working client and emits telemetry."""
    emitted = []

    def fake_ttl_emit(**kwargs):
        emitted.append(kwargs)

    def fake_from_url(*args, **kwargs):
        fake_from_url.kwargs = kwargs
        return MockRedisClient()

    monkeypatch.setattr(redis_utils, "ttl_emit", fake_ttl_emit)
    monkeypatch.setattr(redis_utils.redis.Redis, "from_url", fake_from_url)

    client = redis_utils.get_redis_client()
    assert isinstance(client, MockRedisClient)
    assert fake_from_url.kwargs["socket_connect_timeout"] == 1
    assert fake_from_url.kwargs["socket_timeout"] == 2

    keys = [call["key"] for call in emitted]
    assert redis_utils.REDIS_PING_SUCCESS_KEY in keys
    assert redis_utils.REDIS_PING_KEY in keys


def test_get_redis_client_no_url(monkeypatch, app_context):
    """Returns None and emits error telemetry if REDIS_STORAGE_URI is missing."""
    os.environ.pop("REDIS_STORAGE_URI", None)
    app_context.config.pop("REDIS_STORAGE_URI", None)

    emitted = []

    def fake_ttl_emit(**kwargs):
        emitted.append(kwargs)

    monkeypatch.setattr(redis_utils, "ttl_emit", fake_ttl_emit)

    client = redis_utils.get_redis_client()
    assert client is None
    assert emitted  # error pulse emitted


def test_get_redis_client_tls_flag(monkeypatch, app_context):
    """Adds ssl=True only if URI starts with rediss://."""
    app_context.config["REDIS_STORAGE_URI"] = "rediss://localhost:6379"

    def fake_from_url(*args, **kwargs):
        fake_from_url.kwargs = kwargs
        return MockRedisClient()

    monkeypatch.setattr(redis_utils.redis.Redis, "from_url", fake_from_url)

    redis_utils.get_redis_client()
    assert fake_from_url.kwargs["ssl"] is True
