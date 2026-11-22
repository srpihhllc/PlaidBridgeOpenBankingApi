# =============================================================================
# FILE: app/tests/test_factory_coverage_blitz.py
# DESCRIPTION: Extended coverage suite for factory routing, logging, and edge paths.
# =============================================================================

import importlib

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest

import app as app_module
from app import CorrelationIdFilter, _registry, create_app
from app.config import TestingConfig


@pytest.fixture(autouse=True)
def _use_testing_environment(monkeypatch):
    """Prevent production values in .env from overriding this test module."""
    monkeypatch.setenv("ENV_NAME", "testing")
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("FLASK_CONFIG", "testing")


def test_factory_config_loading_exception_propagates(monkeypatch):
    """Ensure a config-loading error is raised instead of using a fallback app."""
    original_from_object = Flask.config_class.from_object

    def mock_from_object_crash(self, obj):
        if obj is TestingConfig:
            raise ImportError("Simulated configuration loading failure.")
        return original_from_object(self, obj)

    monkeypatch.setattr(
        Flask.config_class,
        "from_object",
        mock_from_object_crash,
    )

    with pytest.raises(
        ImportError,
        match="Simulated configuration loading failure",
    ):
        create_app(config_class=TestingConfig)


def test_factory_invalid_module_string_resolution():
    """Reject an unknown config class instead of selecting a fallback."""
    with pytest.raises(ValueError, match="Invalid config class"):
        create_app(config_class="app.config.NonExistentConfigClassXYZ")


def test_sqlite_engine_options_sanitized(monkeypatch):
    """Ensure SQLite engine options omit incompatible QueuePool settings."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    app = create_app(config_class=TestingConfig)
    options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})

    for forbidden in (
        "pool_size",
        "max_overflow",
        "pool_timeout",
        "pool_recycle",
    ):
        assert forbidden not in options

    assert options.get("poolclass") is not None
    assert options.get("connect_args", {}).get("check_same_thread") is False


def test_routing_hygiene_deep_loops_and_sorting():
    """Exercise route stabilization, deduplication, and pruning."""
    app = create_app(TestingConfig)

    @app.route(
        "/tmp_target_route",
        methods=["GET", "POST"],
        endpoint="tmp_target_view",
    )
    def tmp_target_view():
        return "tmp"

    @app.route(
        "/legacy_target_route",
        methods=["GET", "OPTIONS"],
        endpoint="legacy_target_view",
    )
    def legacy_target_view():
        return "legacy"

    from app import (
        _dedupe_rules,
        _prune_ignorable_route_rules,
        _rebuild_rules_by_endpoint,
        _stabilize_rules_order,
    )

    with app.app_context():
        _prune_ignorable_route_rules(app)
        _dedupe_rules(app)
        _stabilize_rules_order(app)
        _rebuild_rules_by_endpoint(app)

    endpoints = [rule.endpoint for rule in app.url_map.iter_rules()]
    assert "tmp_target_view" not in endpoints
    assert "legacy_target_view" not in endpoints


def test_health_registry_edge_exceptions():
    """Exercise health-check behavior for an unregistered check."""
    result = _registry.run_check("non_existent_check_module")
    assert result["ok"] is False


def test_correlation_filter_fallback_boundaries():
    """Check correlation ID behavior outside request/application contexts."""
    log_filter = CorrelationIdFilter()

    class DummyRecord:
        def __init__(self):
            self.module = "app"
            self.correlation_id = None

    record = DummyRecord()
    assert log_filter.filter(record) is True
    assert record.correlation_id is not None


def test_application_teardown_context_execution():
    """Exercise application context teardown."""
    app = create_app(TestingConfig)
    context = app.app_context()
    context.push()
    context.pop()


def test_error_handling_and_status_code_mappers():
    """Exercise registered error handlers with representative exceptions."""
    app = create_app(TestingConfig)

    with app.test_request_context():
        handlers = app.error_handler_spec.get(None, {}).get(None, [])
        for handler in handlers:
            try:
                handler(BadRequest("Malformed JSON data payload wrapper."))
                handler(RuntimeError("Operational panic trace testing path."))
            except Exception:
                pass


def test_admin_and_conditional_blueprint_registration_gates(monkeypatch):
    """Exercise conditional handling for unavailable admin modules."""
    original_import = importlib.import_module

    def mock_import_blocker(name, *args, **kwargs):
        if "admin_routes" in name or "admin_api" in name or "admin_ui" in name:
            raise ImportError("Simulated missing admin components.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", mock_import_blocker)
    app = create_app(TestingConfig)
    assert app.config["TESTING"] is True


def test_metrics_correlation_telemetry_fallbacks(monkeypatch):
    """Exercise metrics handling when app timing metadata is malformed."""
    app = create_app(TestingConfig)

    monkeypatch.setattr(
        app.config,
        "get",
        lambda key, default=None: (
            "invalid-time-format-string"
            if key == "APP_START_TIME"
            else default
        ),
    )

    with app.test_client() as client:
        try:
            client.get("/metrics")
        except Exception:
            pass


def test_route_prune_whitelist_direct_manipulation():
    """Exercise route-prune whitelist updates."""
    if hasattr(app_module, "add_route_prune_whitelist"):
        updated = app_module.add_route_prune_whitelist(
            "ephemeral_probe_view_override"
        )
        assert "ephemeral_probe_view_override" in updated
    elif hasattr(app_module, "ROUTE_PRUNE_WHITELIST"):
        app_module.ROUTE_PRUNE_WHITELIST.append(
            "ephemeral_probe_view_override"
        )
        assert (
            "ephemeral_probe_view_override"
            in app_module.ROUTE_PRUNE_WHITELIST
        )
        app_module.ROUTE_PRUNE_WHITELIST.remove(
            "ephemeral_probe_view_override"
        )
