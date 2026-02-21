# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_init_smoketests.py


import pytest
from flask import Flask

from app import create_app
from app.config import TestingConfig as TestConfig


@pytest.fixture
def client():
    """Provide a Flask test client using TestConfig."""
    app = create_app(config_class=TestConfig)
    with app.test_client() as client:
        yield client


@pytest.mark.smoketest
def test_fintech_routes_are_versioned(client):
    """Fintech routes must only exist under /api/v1, never at root."""
    rules = [rule.rule for rule in client.application.url_map.iter_rules()]

    # ✅ Expected versioned routes
    assert any(r.startswith("/api/v1/fintech") for r in rules)

    # 🚫 Must not exist at root
    assert not any(r.startswith("/fintech") and not r.startswith("/api/v1") for r in rules)


@pytest.mark.smoketest
def test_healthz_endpoint_schema(client):
    """Health endpoint must return standardized schema with healthy, timestamp, uptime, checks."""
    resp = client.get("/healthz")
    assert resp.status_code in (200, 503)
    data = resp.get_json()

    # Required top-level keys
    for key in ("healthy", "timestamp", "uptime", "checks"):
        assert key in data

    # Checks must include database and redis
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
    assert isinstance(data["healthy"], bool)


@pytest.mark.smoketest
def test_blueprint_registration_logged(caplog):
    """Blueprint registration should log counts per module."""
    with caplog.at_level("INFO"):
        create_app(config_class=TestConfig)
    assert any("Registered" in rec.message and "blueprint" in rec.message for rec in caplog.records)


@pytest.mark.smoketest
def test_fallback_app_guard(monkeypatch, caplog):
    """Importing app outside test env should log CRITICAL and create fallback app."""
    monkeypatch.setenv("FLASK_ENV", "production")
    caplog.set_level("CRITICAL")

    import importlib

    import app as app_module

    importlib.reload(app_module)

    assert any("UNSAFE FALLBACK APP CREATED" in rec.message for rec in caplog.records)
    assert isinstance(app_module.app, Flask)
    assert app_module.app.config["PROPAGATE_EXCEPTIONS"] is False


@pytest.mark.smoketest
def test_jwt_and_login_loaders_registered(client):
    """Ensure Flask-Login and JWT loaders are wired into the app."""
    app = client.application

    # Flask-Login user_loader should be set
    assert app.login_manager._user_callback is not None, "Flask-Login user_loader not registered"

    # JWT blocklist loader should be set
    assert hasattr(
        app.jwt_manager, "token_in_blocklist_callback"
    ), "JWT blocklist loader not registered"
    assert callable(app.jwt_manager.token_in_blocklist_callback)

    # JWT identity loader should be set
    assert hasattr(app.jwt_manager, "user_identity_callback"), "JWT identity loader not registered"
    assert callable(app.jwt_manager.user_identity_callback)


@pytest.mark.smoketest
def test_config_class_name_logged(caplog):
    """App startup should log the actual config class name, not an instance error."""
    with caplog.at_level("INFO"):
        create_app(config_class=TestConfig)
    # Look for the class name string in the logs
    assert any(
        "TestConfig" in rec.message or "DevelopmentConfig" in rec.message for rec in caplog.records
    ), "Config class name not logged correctly"
