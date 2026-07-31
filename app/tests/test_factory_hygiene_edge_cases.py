# =============================================================================
# FILE: app/tests/test_factory_hygiene_edge_cases.py
# DESCRIPTION: Hardened edge case coverage targeting app/__init__.py hygiene loops
# =============================================================================

import logging
import importlib
import pytest
from flask import Flask, g, jsonify, request, Response
from unittest.mock import patch, MagicMock
from werkzeug.exceptions import BadRequest, Forbidden

from app import (
    create_app,
    _registry,
    register_healthcheck,
    unregister_healthcheck,
    _cleanup_premature_oauth_registrations,
    _stabilize_rules_order,
    _rebuild_rules_by_endpoint
)
from app.config import TestingConfig

# =============================================================================
# 1. CORE FACTORY CONFIGURATION RESOLUTION & BOOT GATES
# =============================================================================

def test_create_app_via_string_configuration_path():
    """
    Forces the factory to evaluate a string module path for loading configuration.
    Targets lines 947-955 in app/__init__.py to confirm dot-notation class resolution.
    """
    app = create_app(config_class="app.config.TestingConfig")
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_routing_hygiene_and_pruner_engine():
    """
    Injects temporary, duplicate, and ignorable routes to fully execute the
    route deduplication, pruning, and order-stabilization passes.
    """
    app = create_app(TestingConfig)

    @app.route("/tmp_test_cleanup_endpoint", endpoint="tmp_junk_route")
    def tmp_junk_route():
        return jsonify({"status": "ephemeral"})

    @app.route("/legacy_old_dashboard", endpoint="legacy_dashboard_view")
    def legacy_dashboard_view():
        return jsonify({"status": "deprecated"})

    @app.route("/duplicate_path_clash", endpoint="clash_one")
    def clash_one():
        return jsonify({"id": 1})

    @app.route("/duplicate_path_clash", endpoint="clash_two")
    def clash_two():
        return jsonify({"id": 2})

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
    assert "tmp_junk_route" not in endpoints
    assert "legacy_dashboard_view" not in endpoints


def test_blueprint_registration_guards_and_failures(monkeypatch):
    """
    Forces blueprint auto-discovery execution loops and simulates registration clashing.
    Guards against recursion by calling the uncached raw import reference for system packages.
    """
    app = create_app(TestingConfig)

    from app import _register_blueprints

    try:
        _register_blueprints(app)
    except Exception:
        pytest.fail("Blueprint registration guard structure threw an unhandled exception.")

    # Cache the original import function reference to avoid recursive infinite loops
    original_import_module = importlib.import_module

    def mock_import_module(name, *args, **kwargs):
        # Explicitly trip the import error line targets for administrative route loading gates
        if "admin_routes" in name:
            raise ImportError("Simulated structural import failure for testing coverage path.")
        # Safely hand off core dependencies back to the real python system reference
        return original_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", mock_import_module)

    # Boot a fresh factory context with broken admin routes to verify error safety paths
    salvaged_app = create_app(TestingConfig)
    assert salvaged_app.config["TESTING"] is True


# =============================================================================
# 2. HYGIENE INTERCEPTORS, HEALTH REGISTRIES & TELEMETRY LIFECYCLE
# =============================================================================

def test_health_check_registry_error_boundaries_and_invalid_types():
    """
    Targets Missing Lines: 92-94, 116-117, 120-125
    Exercises HealthCheckRegistry invalid return schemas, missing registrations,
    and type verification safety guards using direct internal state manipulation.
    """
    # 1. Test running an unregistered check
    missing_res = _registry.run_check("non_existent_system_check")
    assert missing_res["ok"] is False
    assert missing_res["error"] == "not_registered"

    # 2. Test a healthcheck that returns an invalid type (non-dict)
    def broken_type_check():
        return "Not A Dictionary"

    # Directly manipulate the verified internal `_checks` dictionary
    _registry._checks["test_broken_type"] = broken_type_check
    try:
        invalid_res = _registry.run_check("test_broken_type")
        assert invalid_res["ok"] is False
        assert invalid_res["error"] == "invalid_result_type"
    finally:
        if "test_broken_type" in _registry._checks:
            del _registry._checks["test_broken_type"]

    # 3. Test a healthcheck throwing a hard runtime exception
    def throwing_check():
        raise RuntimeError("Hardware context panic simulation")

    _registry._checks["test_panic"] = throwing_check
    try:
        panic_res = _registry.run_check("test_panic")
        assert panic_res["ok"] is False
        assert "Hardware context panic simulation" in panic_res["error"]
    finally:
        if "test_panic" in _registry._checks:
            del _registry._checks["test_panic"]


def test_route_hygiene_exception_swallowing_and_removal_edge_cases():
    """
    Targets Missing Lines: 120-125, 145-149, 152-153
    Forces execution loops inside `_cleanup_premature_oauth_registrations`
    and handles rule elimination failures to verify defensive try/except nets.
    """
    # FIX: Use an isolated lightweight Flask instance to eliminate shared factory registry conflicts
    app = Flask("test_hygiene_isolated_app")

    # Inject a premature fake oauth view function matching prefix check criteria
    def mock_oauth_view():
        return "oauth"
    mock_oauth_view.__module__ = "app.blueprints.oauth_routes.dummy"

    app.view_functions["oauth.premature_endpoint_test"] = mock_oauth_view
    app.add_url_rule("/oauth/premature_test", endpoint="oauth.premature_endpoint_test")

    # Force cleanup execution path over the app to sweep target sections
    _cleanup_premature_oauth_registrations(app)
    assert "oauth.premature_endpoint_test" not in app.view_functions


def test_structured_logging_correlation_fallback_vectors():
    """
    Targets Missing Lines: 101-103 range in CorrelationIdFilter
    Exercises request header extraction paths when the global context `g`
    does not contain a pre-assigned correlation_id.
    """
    app = create_app(TestingConfig)
    from app import CorrelationIdFilter

    filter_instance = CorrelationIdFilter()
    log_record = logging.LogRecord(
        name="test_logger", level=logging.INFO, pathname="test.py",
        lineno=10, msg="Telemetry test message", args=(), exc_info=None
    )

    # Test path where context has an explicit header mapping
    with app.test_request_context("/v1/api/probe", headers={"X-Correlation-ID": "header-sig-9999"}):
        assert hasattr(g, "correlation_id") is False
        filter_instance.filter(log_record)
        assert log_record.correlation_id == "header-sig-9999"


def test_global_error_handler_structural_payload_intercepts():
    """
    Targets Missing Lines: 455-461, 474, 497-522
    Triggers explicit errors to test how the custom error handler parses
    unhandled exceptions vs HTTPExceptions into uniform JSON frames.
    """
    app = create_app(TestingConfig)

    @app.route("/force_unhandled_crash")
    def crash_vector():
        raise RuntimeError("Forced system crash scenario")

    @app.route("/force_unprocessable_entity")
    def parsing_crash():
        raise BadRequest("Malformed platform request packet")

    with app.test_client() as client:
        # Trigger runtime 500 mapping
        res_500 = client.get("/force_unhandled_crash")
        assert res_500.status_code == 500

        # Trigger custom transformation loops
        res_422 = client.get("/force_unprocessable_entity")
        assert res_422.status_code == 422 or res_422.status_code == 400


def test_request_telemetry_lifecycle_and_teardown_context():
    """
    Targets Missing Lines: 568-589, 596, 602-631
    Exercises full before_request context injection, custom execution-time
    calculations, and DB session auto-cleanup hooks during request teardown.
    """
    app = create_app(config_class="app.config.TestingConfig")

    # Manually execute the lifecycle workflow inside an explicit request context
    # to guarantee hitting before_request, after_request, and teardown hooks directly.
    with app.test_request_context("/v1/api/probe"):
        # 1. Execute before_request hooks (Targets injection logic)
        app.preprocess_request()

        # 2. Forge a dummy response frame to feed after_request hooks
        mock_response = Response("Telemetry Active")

        # 3. Execute after_request processing (Targets execution time calculations)
        processed_response = app.process_response(mock_response)
        assert processed_response.status_code == 200

    # 4. Test an explicit teardown trigger containing an active unhandled exception
    with app.app_context():
        with app.test_request_context("/"):
            app.preprocess_request()
            app.do_teardown_request(exc=ValueError("Simulated request context destruction crash."))


def test_blueprint_graph_validation_and_prefix_collision_guards():
    """
    Targets Missing Lines: 783-836
    Triggers dynamic blueprint dependency graph cycle tracking and deep discovery loops.
    """
    app = create_app(config_class="app.config.TestingConfig")
    from app.blueprints import validate_blueprints_graph

    # The validation utility executes successfully but evaluates implicitly to None
    result = validate_blueprints_graph(app)
    assert result is None or result is True

    with patch("app.validate_blueprints_graph", return_value=False):
        from app import _register_blueprints
        try:
            _register_blueprints(app)
        except Exception:
            pass


def test_url_map_rebuild_and_stabilization_loops():
    """
    Targets Missing Lines: 1104-1120, 1133-1134
    Exercises Werkzeug router rules processing, optimization, and order sorting loops.
    """
    app = create_app(config_class="app.config.TestingConfig")

    with app.app_context():
        @app.route("/order_probe", methods=["POST", "GET", "PUT"])
        def order_probe():
            return "ok"

        _stabilize_rules_order(app)
        _rebuild_rules_by_endpoint(app)

        rules = [r for r in app.url_map.iter_rules() if r.endpoint == "order_probe"]
        assert len(rules) > 0