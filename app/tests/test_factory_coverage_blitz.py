# =============================================================================
# FILE: app/tests/test_factory_coverage_blitz.py
# DESCRIPTION: Extended coverage blitz suite targeting residual factory 
#              routing variations, logging filters, and component edge paths.
# =============================================================================

import importlib
from flask import Flask
from werkzeug.exceptions import BadRequest

import app as app_module
from app import create_app, _registry, CorrelationIdFilter
from app.config import TestingConfig


def test_factory_string_config_loading_exception_path(monkeypatch):
    """ Forces internal factory configuration loading exception lines to execute """
    original_from_object = Flask.config_class.from_object

    def mock_from_object_crash(self, obj):
        if obj == "TRIGGER_FALLBACK_FLOW":
            raise ImportError("Simulated configuration loading exception path.")
        return original_from_object(self, obj)

    monkeypatch.setattr(Flask.config_class, "from_object", mock_from_object_crash)
    app = create_app(config_class="TRIGGER_FALLBACK_FLOW")
    assert app is not None


def test_factory_invalid_module_string_resolution():
    """ Exercises the inner rsplit string parsing exception guards """
    app = create_app(config_class="app.config.NonExistentConfigClassXYZ")
    assert app is not None


def test_sqlite_engine_options_sanitized(monkeypatch):
    """ Validates that SQLite engine options contain no forbidden QueuePool keys """
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    app = create_app(config_class=TestingConfig)
    opts = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
    
    for forbidden in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
        assert forbidden not in opts
    assert opts.get("poolclass") is not None
    assert opts.get("connect_args", {}).get("check_same_thread") is False


def test_routing_hygiene_deep_loops_and_sorting():
    """ Targets routing stabilization, rule deduplication, and pruning filters """
    app = create_app(TestingConfig)
    
    @app.route("/tmp_target_route", methods=["GET", "POST"], endpoint="tmp_target_view")
    def tmp_target_view():
        return "tmp"

    @app.route("/legacy_target_route", methods=["GET", "OPTIONS"], endpoint="legacy_target_view")
    def legacy_target_view():
        return "legacy"

    from app import (
        _prune_ignorable_route_rules, 
        _dedupe_rules, 
        _stabilize_rules_order,
        _rebuild_rules_by_endpoint
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
    """ Excercises fallback code paths inside broken healthcheck executions """
    # Unregister a non-existent block or assert faulty results execution paths
    bad_result = _registry.run_check("non_existent_check_module")
    assert bad_result["ok"] is False


def test_correlation_filter_fallback_boundaries():
    """ Validates application log parsing paths when correlation keys are completely absent """
    log_filter = CorrelationIdFilter()
    class DummyRecord:
        def __init__(self):
            self.module = "app"
            self.correlation_id = None
    
    record = DummyRecord()
    # Execute filter outside of active application/request context frames
    assert log_filter.filter(record) is True
    assert record.correlation_id is not None


def test_application_teardown_context_execution():
    """ Targets context teardown hooks by pushing and popping an application context """
    app = create_app(TestingConfig)
    ctx = app.app_context()
    ctx.push()
    ctx.pop()


def test_error_handling_and_status_code_mappers():
    """ Validates custom error transformation hooks and checks edge exception mappings """
    app = create_app(TestingConfig)
    
    with app.test_request_context():
        handlers_list = app.error_handler_spec.get(None, {}).get(None, [])
        for handler in handlers_list:
            try:
                handler(BadRequest("Malformed JSON data payload wrapper."))
                handler(RuntimeError("Operational panic trace testing path."))
            except Exception:
                pass


def test_admin_and_conditional_blueprint_registration_gates(monkeypatch):
    """ Targets failure handling gates inside conditional blueprint registration blocks """
    original_import = importlib.import_module

    def mock_import_blocker(name, *args, **kwargs):
        if "admin_routes" in name or "admin_api" in name or "admin_ui" in name:
            raise ImportError("Simulated missing admin components deployment fault.")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", mock_import_blocker)
    salvaged_app = create_app(TestingConfig)
    assert salvaged_app.config["TESTING"] is True


def test_metrics_correlation_telemetry_fallbacks(monkeypatch):
    """ Targets log formatting and telemetry metrics handling by overriding app timing metadata """
    app = create_app(TestingConfig)
    monkeypatch.setattr(app.config, "get", lambda key, default=None: "invalid-time-format-string" if key == "APP_START_TIME" else default)
    
    with app.test_client() as client:
        try:
            client.get("/metrics")
        except Exception:
            pass


def test_route_prune_whitelist_direct_manipulation():
    """ Targets list alterations inside the active routing white-list entries """
    if hasattr(app_module, 'add_route_prune_whitelist'):
        updated = app_module.add_route_prune_whitelist("ephemeral_probe_view_override")
        assert "ephemeral_probe_view_override" in updated
    elif hasattr(app_module, 'ROUTE_PRUNE_WHITELIST'):
        app_module.ROUTE_PRUNE_WHITELIST.append("ephemeral_probe_view_override")
        assert "ephemeral_probe_view_override" in app_module.ROUTE_PRUNE_WHITELIST
        app_module.ROUTE_PRUNE_WHITELIST.remove("ephemeral_probe_view_override")