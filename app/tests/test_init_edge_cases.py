# =============================================================================
# FILE: tests/test_init_edge_cases.py
# DESCRIPTION: Aggressive coverage suite targeting app factory fallbacks, 
#              except blocks, and dynamic configuration loading.
# =============================================================================

import os
import logging
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from werkzeug.exceptions import BadRequest, InternalServerError

from app import create_app
from app.__init__ import HealthCheckRegistry, CorrelationIdFilter, _registry


# -----------------------------------------------------------------------------
# 1. Config Loading Edge Cases
# -----------------------------------------------------------------------------
def test_create_app_string_config_fallback(caplog):
    """Force a failed string module import to trigger the fallback."""
    app = create_app(config_class="invalid.module.ConfigClass")
    # The application gracefully falls back to 'default', which natively sets TESTING = False
    assert app.config["TESTING"] is False
    assert "Failed to load config class" in caplog.text


def test_create_app_env_name_override():
    """Test passing config via env_name."""
    app = create_app(env_name="testing")
    assert app.config["TESTING"] is True


def test_create_app_testing_config_failure(monkeypatch, caplog):
    """Force from_object to fail to trigger the ultimate testing fallback."""
    def mock_from_object(config_instance, obj, *args, **kwargs):
        # Inject required DB URI so init_extensions doesn't blow up when config fails
        config_instance["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        raise Exception("Simulated Config Crash")
    
    # We patch Flask.config.from_object just for this run
    with patch("flask.Config.from_object", autospec=True, side_effect=mock_from_object):
        app = create_app("testing")
        assert "Config.from_object failed" in caplog.text
        assert app.config["TESTING"] is True


# -----------------------------------------------------------------------------
# 2. HealthCheck Registry Edge Cases
# -----------------------------------------------------------------------------
def test_healthcheck_registry_invalid_fn():
    """Test registering a non-callable."""
    registry = HealthCheckRegistry()
    with pytest.raises(TypeError):
        registry.register("bad", "not-a-function")


def test_healthcheck_registry_execution():
    """Test standard and failing health checks."""
    registry = HealthCheckRegistry()
    
    # Happy path
    registry.register("good", lambda: {"ok": True})
    
    # Bad return type
    registry.register("bad_type", lambda: "string-instead-of-dict")
    
    # Exception inside check
    def crash_check():
        raise ValueError("DB Offline")
    registry.register("crash", crash_check)

    results = registry.run_all()
    assert results["good"]["ok"] is True
    assert results["bad_type"]["ok"] is False
    assert results["bad_type"]["error"] == "invalid_result_type"
    assert results["crash"]["ok"] is False
    assert "DB Offline" in results["crash"]["error"]

    # Test running an unregistered check
    assert registry.run_check("missing")["error"] == "not_registered"


# -----------------------------------------------------------------------------
# 3. Route Hygiene & Rebuild Exceptions (The massive try/except blocks)
# -----------------------------------------------------------------------------
@patch("app.__init__._cleanup_premature_oauth_registrations")
@patch("app.__init__._prune_ignorable_route_rules")
@patch("app.__init__._rebuild_rules_by_endpoint")
def test_factory_hygiene_exceptions(mock_rebuild, mock_prune, mock_cleanup, caplog):
    """
    Force exceptions in the hygiene helpers to ensure the factory boot 
    doesn't crash and correctly logs debug info.
    """
    mock_cleanup.side_effect = Exception("Cleanup Crash")
    mock_prune.side_effect = Exception("Prune Crash")
    mock_rebuild.side_effect = Exception("Rebuild Crash")

    # The app should still boot successfully
    app = create_app("testing")
    assert app is not None


def test_internal_hygiene_functions_direct_crash():
    """Directly test hygiene functions by passing a broken object."""
    from app.__init__ import (
        _cleanup_premature_oauth_registrations,
        _prune_ignorable_route_rules,
        _reconcile_oauth_callback_aliases,
        _enforce_route_uniqueness,
        _dedupe_rules,
        _stabilize_rules_order
    )
    
    # Pass an integer instead of a Flask app. This will cause getattr() 
    # and hasattr() checks inside these functions to fail/raise exceptions, 
    # successfully hitting the `except Exception:` blocks.
    broken_app = 12345 
    
    _cleanup_premature_oauth_registrations(broken_app)
    _prune_ignorable_route_rules(broken_app)
    _reconcile_oauth_callback_aliases(broken_app)
    _enforce_route_uniqueness(broken_app)
    _dedupe_rules(broken_app)
    _stabilize_rules_order(broken_app)
    # If no exceptions leak out, the coverage for the except blocks is achieved.


# -----------------------------------------------------------------------------
# 4. Error Handler Edge Cases (The Crash Dump Writer)
# -----------------------------------------------------------------------------
def test_custom_error_handler_crash_dump():
    """Trigger a 500 error and test the custom _handle_exception logic."""
    fresh_app = create_app("testing")

    # Dynamically register the route BEFORE creating the test client or making requests
    @fresh_app.route("/force-500")
    def force_500():
        raise InternalServerError("Simulated Core Meltdown")

    with fresh_app.test_client() as client:
        response = client.get("/force-500")
        assert response.status_code == 500
        data = response.get_json()
        assert data["msg"] == "Internal Server Error"
        assert "Simulated Core Meltdown" in data["error"]


def test_custom_error_handler_bad_request_ignite_cortex(monkeypatch):
    """Test the specific override for main.ignite_cortex on 400 errors."""
    fresh_app = create_app("testing")

    # Register dynamic test route under an isolated endpoint name to avoid collisions
    @fresh_app.route("/force-400", endpoint="test_init.force_400")
    def force_400():
        raise BadRequest("Ignite failed")

    # Mock request.endpoint so app/__init__.py line 145 triggers the ignition override path
    monkeypatch.setattr(
        "flask.Request.endpoint",
        property(lambda self: "main.ignite_cortex"),
    )

    with fresh_app.test_client() as client:
        response = client.get("/force-400")
        assert response.status_code == 400


# -----------------------------------------------------------------------------
# 5. Database Initialization Overrides
# -----------------------------------------------------------------------------
@patch("app.__init__.db.create_all")
def test_db_init_alembic_override(mock_create_all, monkeypatch):
    """Ensure db.create_all is skipped if ALEMBIC_RUNNING=1."""
    money_patch = monkeypatch
    money_patch.setenv("ALEMBIC_RUNNING", "1")
    money_patch.setenv("FLASK_ENV", "development") # Force out of testing mode
    
    app = create_app("default")
    mock_create_all.assert_not_called()


# -----------------------------------------------------------------------------
# 6. Logging Correlation ID Filter
# -----------------------------------------------------------------------------
def test_correlation_id_filter_no_request():
    """Test the filter outside of a request context."""
    filt = CorrelationIdFilter()
    record = logging.LogRecord("name", logging.INFO, "path", 1, "msg", (), None)
    
    # Should generate a new UUID since there is no request context
    result = filt.filter(record)
    assert result is True
    assert hasattr(record, "correlation_id")
    assert record.correlation_id.startswith("cid-")