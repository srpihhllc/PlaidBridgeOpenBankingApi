# =============================================================================
# FILE: tests/test_init_edge_cases.py
# DESCRIPTION: Aggressive coverage suite targeting app factory fallbacks,
#              exception handlers, route hygiene, and dynamic configuration.
# =============================================================================

import logging
from unittest.mock import patch

import pytest
from werkzeug.exceptions import BadRequest, InternalServerError

from app import create_app
from app.__init__ import CorrelationIdFilter, HealthCheckRegistry


# -----------------------------------------------------------------------------
# Configuration loading edge cases
# -----------------------------------------------------------------------------
def test_create_app_string_config_fallback(caplog):
    """An invalid config import should fall back to the default config."""
    caplog.set_level(logging.DEBUG)

    application = create_app(
        config_class="invalid.module.ConfigClass",
    )

    assert application.config["TESTING"] is False
    assert "Failed to load config class" in caplog.text


def test_create_app_env_name_override():
    """The env_name argument should select the requested configuration."""
    application = create_app(env_name="testing")

    assert application.config["TESTING"] is True


def test_create_app_testing_config_failure(caplog):
    """A testing config failure should use the testing fallback."""

    def failing_from_object(config_instance, obj, *args, **kwargs):
        # Preserve the database setting required by extension initialization.
        config_instance["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        raise RuntimeError("Simulated Config Crash")

    caplog.set_level(logging.DEBUG)

    with patch(
        "flask.Config.from_object",
        autospec=True,
        side_effect=failing_from_object,
    ):
        application = create_app("testing")

    assert application.config["TESTING"] is True
    assert "Config.from_object failed" in caplog.text


# -----------------------------------------------------------------------------
# Health-check registry edge cases
# -----------------------------------------------------------------------------
def test_healthcheck_registry_rejects_non_callable():
    """Registering a non-callable health check should raise TypeError."""
    registry = HealthCheckRegistry()

    with pytest.raises(TypeError):
        registry.register("bad", "not-a-function")


def test_healthcheck_registry_runs_successful_and_failing_checks():
    """The registry should normalize invalid results and raised exceptions."""
    registry = HealthCheckRegistry()

    registry.register("good", lambda: {"ok": True})
    registry.register("bad_type", lambda: "string-instead-of-dict")

    def crash_check():
        raise ValueError("DB Offline")

    registry.register("crash", crash_check)

    results = registry.run_all()

    assert results["good"] == {"ok": True}

    assert results["bad_type"]["ok"] is False
    assert results["bad_type"]["error"] == "invalid_result_type"

    assert results["crash"]["ok"] is False
    assert "DB Offline" in results["crash"]["error"]

    assert registry.run_check("missing")["error"] == "not_registered"


# -----------------------------------------------------------------------------
# Route hygiene and rebuild exception handling
# -----------------------------------------------------------------------------
@patch("app.__init__._rebuild_rules_by_endpoint")
@patch("app.__init__._prune_ignorable_route_rules")
@patch("app.__init__._cleanup_premature_oauth_registrations")
def test_factory_hygiene_exceptions(
    mock_cleanup,
    mock_prune,
    mock_rebuild,
    caplog,
):
    """
    Exceptions raised by factory route-hygiene helpers should be caught so
    application creation can continue.
    """
    caplog.set_level(logging.DEBUG)

    mock_cleanup.side_effect = RuntimeError("Cleanup Crash")
    mock_prune.side_effect = RuntimeError("Prune Crash")
    mock_rebuild.side_effect = RuntimeError("Rebuild Crash")

    application = create_app("testing")

    assert application is not None


def test_route_hygiene_helpers_swallow_top_level_exceptions():
    """
    Route-hygiene helpers should not leak exceptions when given an invalid
    application object.

    Their outer exception handlers must use the module logger rather than
    app.logger because the invalid object has no logger attribute.
    """
    from app.__init__ import (
        _cleanup_premature_oauth_registrations,
        _dedupe_rules,
        _enforce_route_uniqueness,
        _prune_ignorable_route_rules,
        _reconcile_oauth_callback_aliases,
        _stabilize_rules_order,
    )

    broken_app = 12345

    _cleanup_premature_oauth_registrations(broken_app)
    _prune_ignorable_route_rules(broken_app)
    _reconcile_oauth_callback_aliases(broken_app)
    _enforce_route_uniqueness(broken_app)
    _dedupe_rules(broken_app)
    _stabilize_rules_order(broken_app)


# -----------------------------------------------------------------------------
# Error-handler edge cases
# -----------------------------------------------------------------------------
def test_custom_error_handler_returns_crash_dump():
    """The custom error handler should return structured 500 JSON."""
    application = create_app("testing")

    @application.route("/force-500")
    def force_500():
        raise InternalServerError("Simulated Core Meltdown")

    with application.test_client() as client:
        response = client.get("/force-500")

    assert response.status_code == 500

    data = response.get_json()
    assert data is not None
    assert data["msg"] == "Internal Server Error"
    assert "Simulated Core Meltdown" in data["error"]


def test_custom_error_handler_handles_ignite_cortex_bad_request(monkeypatch):
    """
    A 400 response for main.ignite_cortex should execute the dedicated
    endpoint-specific error-handler branch.
    """
    application = create_app("testing")

    @application.route(
        "/force-400",
        endpoint="test_init.force_400",
    )
    def force_400():
        raise BadRequest("Ignite failed")

    monkeypatch.setattr(
        "flask.Request.endpoint",
        property(lambda self: "main.ignite_cortex"),
    )

    with application.test_client() as client:
        response = client.get("/force-400")

    assert response.status_code == 400


# -----------------------------------------------------------------------------
# Database initialization overrides
# -----------------------------------------------------------------------------
@patch("app.__init__.db.create_all")
def test_db_initialization_skips_create_all_during_alembic(
    mock_create_all,
    monkeypatch,
):
    """db.create_all should not run while Alembic is active."""
    monkeypatch.setenv("ALEMBIC_RUNNING", "1")
    monkeypatch.setenv("FLASK_ENV", "development")

    create_app("default")

    mock_create_all.assert_not_called()


# -----------------------------------------------------------------------------
# Correlation-ID logging filter
# -----------------------------------------------------------------------------
def test_correlation_id_filter_without_request_context():
    """The filter should generate a correlation ID outside a request."""
    correlation_filter = CorrelationIdFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test_init_edge_cases.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )

    assert correlation_filter.filter(record) is True
    assert hasattr(record, "correlation_id")
    assert record.correlation_id.startswith("cid-")
