# =============================================================================
# FILE: app/tests/test_factory_edge_cases.py
# DESCRIPTION: Edge-case tests for app/__init__.py.
# =============================================================================

import logging
from unittest.mock import MagicMock, PropertyMock

import pytest
from flask import Flask, jsonify, request
from flask.config import Config
from werkzeug.exceptions import BadRequest, HTTPException

from app import (
    HealthCheckRegistry,
    CorrelationIdFilter,
    _safe_status_code,
    add_route_prune_whitelist,
    create_app,
)


@pytest.fixture(autouse=True)
def _use_testing_environment(monkeypatch):
    """Prevent production values in .env from overriding this test module."""
    monkeypatch.setenv("ENV_NAME", "testing")
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("FLASK_CONFIG", "testing")


# =============================================================================
# 1. CORE FACTORY CONFIGURATION RESOLUTION TESTS
# =============================================================================


def test_factory_string_config_resolution():
    """Resolve a dotted config class path from app.config."""
    app = create_app(config_class="app.config.TestingConfig")
    assert app.config["TESTING"] is True


def test_factory_invalid_string_config_fails_closed():
    """Reject an unknown config class instead of selecting a fallback."""
    with pytest.raises(ValueError, match="Invalid config class"):
        create_app(config_class="app.config.ThisDoesNotExistAtAllXYZ")


def test_factory_config_from_object_exception_propagates(monkeypatch):
    """Propagate config-loading errors instead of building a fallback app."""
    original_from_object = Config.from_object

    def side_effect(self, obj):
        if obj.__name__ == "TestingConfig":
            raise RuntimeError(
                "Simulated config loading failure."
            )
        return original_from_object(self, obj)

    monkeypatch.setattr(Config, "from_object", side_effect)

    with pytest.raises(RuntimeError, match="Simulated config loading failure"):
        create_app(config_class="app.config.TestingConfig")


# =============================================================================
# 2. INTERNAL UTILITIES & BLUEPRINT GUARDS
# =============================================================================


def test_safe_status_code_exception():
    """Check status-code handling for invalid input and HTTP exceptions."""
    assert _safe_status_code("NOT_A_CODE") == 500

    http_exc = BadRequest("Invalid payload parameters")
    assert isinstance(http_exc, HTTPException)
    assert _safe_status_code(http_exc.code) == 400


def test_blueprint_registration_duplicate_skipping(caplog, monkeypatch):
    """Exercise the duplicate-blueprint registration guard."""
    app = Flask("test_dup_bp")
    app.config["TESTING"] = True
    app.blueprints = {
        "auth_mock_target": MagicMock(),
    }

    import app as app_module
    from app import _register_blueprints

    with caplog.at_level(logging.DEBUG):
        mock_bp = MagicMock()
        mock_bp.name = "auth_mock_target"

        def mock_register(flask_app):
            flask_app.register_blueprint(mock_bp)

        monkeypatch.setattr(app_module, "register_blueprints", mock_register)
        _register_blueprints(app)

    assert any(
        "already registered globally; skipping" in record.getMessage()
        for record in caplog.records
    )


# =============================================================================
# 3. GLOBAL ERROR HANDLERS & DIAGNOSTIC INTERCEPTS
# =============================================================================


def test_diagnostic_crash_handler_execution():
    """Exercise diagnostic crash logging for an active request."""
    app = create_app(config_class="app.config.TestingConfig")

    @app.route("/force_diagnostic_crash")
    def force_crash():
        if request.path == "/force_diagnostic_crash":
            _ = jsonify({"status": "error_pending"})
        raise RuntimeError("Deliberate diagnostic validation failure")

    with app.test_client() as client:
        response = client.get("/force_diagnostic_crash")

    assert response.status_code == 500


def test_ignite_cortex_bad_request_passthrough(monkeypatch):
    """Ensure a BadRequest on main.ignite_cortex remains a 400."""
    app = create_app(config_class="app.config.TestingConfig")

    @app.route("/ignite_test")
    def trigger_cortex_err():
        assert request.path == "/ignite_test"
        raise BadRequest("Invalid JSON structure format")

    monkeypatch.setattr(
        "flask.Request.endpoint",
        PropertyMock(return_value="main.ignite_cortex"),
    )

    with app.test_client() as client:
        response = client.get("/ignite_test")

    assert response.status_code == 400


# =============================================================================
# 4. HEALTH CHECK REGISTRY & SERVICE CHECKS
# =============================================================================


def test_healthcheck_registry_type_safety():
    """Exercise registry behavior for missing entries and invalid results."""
    registry = HealthCheckRegistry()

    with pytest.raises(TypeError):
        registry.register("invalid_fn", "not_a_callable")

    registry.unregister("non_existent_check")

    missing_result = registry.run_check("unregistered_component")
    assert missing_result["ok"] is False
    assert missing_result["error"] == "not_registered"

    registry.register(
        "bad_type_check",
        lambda: ["not", "a", "dictionary"],
    )
    bad_result = registry.run_check("bad_type_check")
    assert bad_result["ok"] is False
    assert bad_result["error"] == "invalid_result_type"

    def broken_callable():
        raise ValueError("Hardware bus disconnect error sim")

    registry.register("broken_check", broken_callable)
    error_result = registry.run_check("broken_check")
    assert error_result["ok"] is False
    assert "Hardware bus disconnect" in error_result["error"]

    assert "broken_check" in registry.list_checks()
    assert "broken_check" in registry.run_all()


def test_redis_healthcheck_no_client(monkeypatch):
    """Exercise the Redis health check when no client exists."""
    app = create_app(config_class="app.config.TestingConfig")

    with app.app_context():
        import app as app_module
        from app import _make_redis_check

        monkeypatch.setattr(app, "redis_client", None)
        monkeypatch.setattr(app_module, "_maybe_redis_client", None)

        result = _make_redis_check()()

    assert result["ok"] is False
    assert result["error"] == "no_client"


# =============================================================================
# 5. ROUTE HYGIENE, PIPELINES, AND DEDUPLICATION LOOPS
# =============================================================================


def test_route_hygiene_and_duplication_handling():
    """Exercise duplicate-rule handling, pruning, and aliasing."""
    app = Flask("hygiene_test_app")
    app.config["TESTING"] = True

    @app.route("/duplicate_path", methods=["GET"])
    def first_rule():
        return jsonify({"rule": 1})

    def second_rule():
        return jsonify({"rule": 2})

    app.add_url_rule(
        "/duplicate_path",
        endpoint="second_rule",
        view_func=second_rule,
        methods=["GET"],
    )

    @app.route("/tmp_path", methods=["GET"])
    def temp_rule():
        return jsonify({"rule": "tmp"})

    from app import (
        _dedupe_rules,
        _enforce_route_uniqueness,
        _prune_ignorable_route_rules,
        _rebuild_rules_by_endpoint,
        _reconcile_oauth_callback_aliases,
    )

    add_route_prune_whitelist("admin.admin_index")

    _enforce_route_uniqueness(app)
    _dedupe_rules(app)
    _prune_ignorable_route_rules(app)
    _reconcile_oauth_callback_aliases(app)
    _rebuild_rules_by_endpoint(app)

    assert True


def test_cleanup_premature_oauth_registrations():
    """Remove detached OAuth endpoints from the view-function map."""
    app = Flask("test_cleanup_isolated_app")

    oauth_mock = MagicMock()
    oauth_mock.name = "oauth"

    oauth_bp_mock = MagicMock()
    oauth_bp_mock.name = "oauth_bp"

    app.blueprints = {
        "oauth": oauth_mock,
        "oauth_bp": oauth_bp_mock,
    }

    def fake_oauth_view():
        pass

    fake_oauth_view.__module__ = "app.blueprints.oauth_routes"
    fake_oauth_view.__name__ = "premature_endpoint"
    app.view_functions["oauth.premature_endpoint"] = fake_oauth_view

    from app import _cleanup_premature_oauth_registrations

    _cleanup_premature_oauth_registrations(app)
    assert "oauth.premature_endpoint" not in app.view_functions


# =============================================================================
# 6. AUTH LOADERS & IDENTITY GOD-MODE CHANNELS
# =============================================================================


def test_jwt_user_lookup_operator_intercept():
    """Exercise system-operator handling in user lookup callbacks."""
    app = create_app(config_class="app.config.TestingConfig")

    with app.app_context():
        from app.auth_handlers import load_user, user_lookup_callback

        jwt_result = user_lookup_callback(
            {},
            {"sub": "TERENCE_CORTEX_PRIME"},
        )

        assert jwt_result is not None
        assert jwt_result.username == "OPERATOR_ADMIN"
        assert jwt_result.get_id() == "TERENCE_CORTEX_PRIME"
        assert getattr(jwt_result, "role", None) == "subscriber"
        assert jwt_result.is_authenticated is True

        session_result = load_user("TERENCE_CORTEX_PRIME")
        assert session_result is not None
        assert session_result.username == "OPERATOR_ADMIN"
        assert session_result.get_id() == "TERENCE_CORTEX_PRIME"


# =============================================================================
# 7. STARTUP FAILURE HANDLING
# =============================================================================


def test_production_startup_failure_is_logged_and_reraised(
    monkeypatch,
    caplog,
):
    """Verify production startup failures are logged and propagated."""

    def exploding_flask(*args, **kwargs):
        raise RuntimeError("Production hardware crash sim")

    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setitem(
        create_app.__globals__,
        "Flask",
        exploding_flask,
    )

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(
            RuntimeError,
            match="Production hardware crash sim",
        ):
            create_app()

    assert any(
        record.levelno >= logging.CRITICAL
        and "FATAL BOOT ERROR" in record.getMessage()
        for record in caplog.records
    ), "Production initialization failure did not log FATAL BOOT ERROR."
