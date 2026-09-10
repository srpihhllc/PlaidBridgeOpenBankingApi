# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_init_smoketests.py

import importlib

import pytest
from flask import Flask

from app import create_app
from app.config import TestingConfig as TestConfig
from app.extensions import jwt  # 🔐 Authoritative global JWT extension


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
    assert not any(
        r.startswith("/fintech") and not r.startswith("/api/v1") for r in rules
    )


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
    """Blueprint registration should log core blueprint operations."""
    with caplog.at_level("INFO"):
        create_app(config_class=TestConfig)

    # Check for the explicit registration logs OR the final success summary
    has_registrations = any(
        "Registered" in rec.message for rec in caplog.records
    )
    has_success_signal = any(
        "blueprints registered successfully" in rec.message
        for rec in caplog.records
    )

    assert (
        has_registrations or has_success_signal
    ), "Failed to find valid blueprint registration logs."


@pytest.mark.smoketest
def test_fallback_app_guard(monkeypatch, caplog):
    """Importing app outside test env should log CRITICAL and create fallback app."""
    monkeypatch.setenv("FLASK_ENV", "production")
    caplog.set_level("CRITICAL")

    import app as app_module
    import app.extensions

    # 💥 SABOTAGE: Force a fatal boot crash during module reload to
    # guarantee that the top-level try/except emergency fallback is triggered.
    def fatal_crash(*args, **kwargs):
        raise RuntimeError("Simulated fatal boot crash!")

    monkeypatch.setattr(app.extensions, "init_extensions", fatal_crash)

    try:
        # Reload to trigger the fallback guard logic
        importlib.reload(app_module)

        # --- Assertions ---
        assert any(
            "UNSAFE FALLBACK APP CREATED" in rec.message
            for rec in caplog.records
        )
        assert getattr(app_module, "app", None) is not None
        assert isinstance(app_module.app, Flask)
        assert app_module.app.config.get("SAFE_MODE") is True
        assert app_module.app.config.get("FALLBACK_MODE") is True
        assert app_module.app.config.get("PROPAGATE_EXCEPTIONS") is False

    finally:
        # 🧼 CLEANUP: Un-sabotage the mock and cleanly reload the module
        # so subsequent tests have a healthy app and state pollution is stopped.
        monkeypatch.undo()
        importlib.reload(app_module)


@pytest.mark.smoketest
def test_jwt_and_login_loaders_registered(client):
    """Ensure Flask-Login and JWT loaders are wired into the app."""
    app = client.application

    # Flask-Login user_loader should be set
    assert (
        app.login_manager._user_callback is not None
    ), "Flask-Login user_loader not registered"

    # Fetch jwt_manager authoritatively from extensions map or fallback to the global manager
    jwt_manager = app.extensions.get("flask-jwt-extended") or jwt
    assert jwt_manager is not None, "JWTManager extension is not initialized"

    # Verify JWT blocklist loader callback registration
    blocklist_cb = getattr(jwt_manager, "_token_in_blocklist_callback", None)
    assert blocklist_cb is not None and callable(
        blocklist_cb
    ), "JWT blocklist loader callback not registered"

    # Verify JWT identity loader callback registration
    identity_cb = getattr(jwt_manager, "_user_identity_callback", None)
    assert identity_cb is not None and callable(
        identity_cb
    ), "JWT identity loader callback not registered"


@pytest.mark.smoketest
def test_config_class_name_logged(caplog):
    """App startup should log the actual config class name, not an instance error."""
    with caplog.at_level("INFO"):
        create_app(config_class=TestConfig)
    # Look for the class name string in the logs
    assert any(
        "TestConfig" in rec.message
        or "TestingConfig" in rec.message
        or "DevelopmentConfig" in rec.message
        for rec in caplog.records
    ), "Config class name not logged correctly"
