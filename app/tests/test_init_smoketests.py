# =============================================================================
# FILE: app/tests/test_init_smoketests.py
# DESCRIPTION: Smoke tests for application bootstrap, health endpoints,
# blueprint registration, JWT wiring, and emergency fallback protections.
# =============================================================================

import importlib
import logging

import pytest
from flask import Flask

from app import create_app
from app.config import TestingConfig as TestConfig
from app.extensions import jwt


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def client():
    """Provide a Flask test client using TestConfig."""
    app = create_app(config_class=TestConfig)

    with app.test_client() as test_client:
        yield test_client


# =============================================================================
# ROUTING SMOKETESTS
# =============================================================================


@pytest.mark.smoketest
def test_fintech_routes_are_versioned(client):
    """Fintech routes must only exist under /api/v1."""
    rules = [rule.rule for rule in client.application.url_map.iter_rules()]

    assert any(rule.startswith("/api/v1/fintech") for rule in rules)

    assert not any(
        rule.startswith("/fintech") and not rule.startswith("/api/v1")
        for rule in rules
    )


@pytest.mark.smoketest
def test_healthz_endpoint_schema(client):
    """Health endpoint must return the standard health schema."""
    response = client.get("/healthz")

    assert response.status_code in (200, 503)

    data = response.get_json()

    assert data is not None

    for key in ("healthy", "timestamp", "uptime", "checks"):
        assert key in data

    assert "database" in data["checks"]
    assert "redis" in data["checks"]
    assert isinstance(data["healthy"], bool)


# =============================================================================
# BOOTSTRAP LOGGING
# =============================================================================


@pytest.mark.smoketest
def test_blueprint_registration_logged(caplog):
    """
    Blueprint registration should emit registration logs or final
    registration success logs.
    """
    with caplog.at_level(logging.INFO):
        create_app(config_class=TestConfig)

    has_registration_log = any(
        "Registered" in record.getMessage() for record in caplog.records
    )

    has_success_log = any(
        "blueprints registered successfully" in record.getMessage().lower()
        for record in caplog.records
    )

    assert (
        has_registration_log or has_success_log
    ), "Failed to locate blueprint registration logs."


# =============================================================================
# FALLBACK SENTINEL VALIDATION
# =============================================================================


@pytest.mark.smoketest
def test_fallback_app_guard(monkeypatch, caplog):
    """
    Force a fatal initialization crash and verify that the emergency fallback
    application is created.
    """
    monkeypatch.setenv("FLASK_ENV", "production")

    import app as app_module
    import app.extensions

    def fatal_crash(*args, **kwargs):
        raise RuntimeError("Simulated fatal boot crash!")

    monkeypatch.setattr(
        app.extensions,
        "init_extensions",
        fatal_crash,
    )

    try:
        with caplog.at_level(logging.INFO):
            importlib.reload(app_module)

        fatal_messages = [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.CRITICAL
        ]

        fallback_messages = [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.ERROR
        ]

        assert any(
            "FATAL BOOT ERROR" in message
            for message in fatal_messages
        ), (
            "Missing fatal boot log. "
            f"Captured critical messages: {fatal_messages}"
        )

        assert any(
            "Emergency Safe-Mode Fallback App initialized" in message
            for message in fallback_messages
        ), (
            "Missing fallback log. "
            f"Captured error messages: {fallback_messages}"
        )

        assert getattr(app_module, "app", None) is not None
        assert isinstance(app_module.app, Flask)

        assert app_module.app.config.get("SAFE_MODE") is True
        assert app_module.app.config.get("FALLBACK_MODE") is True
        assert app_module.app.config.get("PROPAGATE_EXCEPTIONS") is False

    finally:
        monkeypatch.undo()
        importlib.reload(app_module)


# =============================================================================
# JWT / LOGIN-MANAGER WIRING
# =============================================================================


@pytest.mark.smoketest
def test_jwt_and_login_loaders_registered(client):
    """Ensure Flask-Login and JWT callbacks are registered."""
    app = client.application

    assert app.login_manager._user_callback is not None, (
        "Flask-Login user_loader not registered"
    )

    jwt_manager = app.extensions.get("flask-jwt-extended") or jwt

    assert jwt_manager is not None, "JWTManager extension not initialized"

    blocklist_callback = getattr(
        jwt_manager,
        "_token_in_blocklist_callback",
        None,
    )

    assert (
        blocklist_callback is not None
        and callable(blocklist_callback)
    ), "JWT blocklist callback not registered"

    identity_callback = getattr(
        jwt_manager,
        "_user_identity_callback",
        None,
    )

    assert (
        identity_callback is not None
        and callable(identity_callback)
    ), "JWT identity callback not registered"


# =============================================================================
# CONFIGURATION LOGGING
# =============================================================================


@pytest.mark.smoketest
def test_config_class_name_logged(caplog):
    """Startup should log a valid config class name."""
    with caplog.at_level(logging.INFO):
        create_app(config_class=TestConfig)

    assert any(
        (
            "TestConfig" in record.getMessage()
            or "TestingConfig" in record.getMessage()
            or "DevelopmentConfig" in record.getMessage()
        )
        for record in caplog.records
    ), "Config class name not logged correctly"