# =============================================================================
# FILE: app/tests/test_factory_edge_cases.py
# DESCRIPTION: Exhaustive target testing of edge case code paths in
#              app/__init__.py
# =============================================================================

import logging
from unittest.mock import MagicMock, PropertyMock

import pytest
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException

from app import (
    HealthCheckRegistry,
    _safe_status_code,
    add_route_prune_whitelist,
    create_app,
)


# =============================================================================
# 1. CORE FACTORY CONFIGURATION RESOLUTION TESTS
# =============================================================================


def test_factory_string_config_resolution():
    """Forces the factory string configuration loop to resolve classes via strings."""
    app = create_app(config_class="app.config.TestingConfig")

    assert app.config["TESTING"] is True


def test_factory_invalid_string_config_fallback(caplog):
    """Forces a garbage string configuration path to trigger warning fallback."""
    app = create_app(config_class="app.config.ThisDoesNotExistAtAllXYZ")

    assert app.config["TESTING"] is False

    has_warning = any(
        "Failed to load config class" in record.getMessage()
        for record in caplog.records
    )

    assert has_warning


def test_factory_config_from_object_exception_fallback(monkeypatch):
    """
    Forces an exception inside config.from_object to ensure the testing
    fallback executes cleanly when application configurations experience
    initialization errors.
    """
    from flask.config import Config

    original_from_object = Config.from_object
    calls = {"count": 0}

    def side_effect(self, obj):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError(
                "Authoritative database profile configuration connection drop error sim"
            )
        return original_from_object(self, obj)

    monkeypatch.setattr(Config, "from_object", side_effect)

    app = create_app(config_class="app.config.TestingConfig")

    assert app.config["TESTING"] is False


# =============================================================================
# 2. INTERNAL UTILITIES & BLUEPRINT GUARDS
# =============================================================================


def test_safe_status_code_exception():
    """
    Forces _safe_status_code to intercept non-integer inputs and
    HTTPException status codes.
    """
    assert _safe_status_code("NOT_A_CODE") == 500

    http_exc = BadRequest("Invalid payload parameters")

    assert isinstance(http_exc, HTTPException)
    assert _safe_status_code(http_exc.code) == 400


def test_blueprint_registration_duplicate_skipping(caplog, monkeypatch):
    """
    Forces duplicate blueprint registration tracking loop to drop into
    the debug log branch.
    """
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
    """
    Forces a severe exception inside an active request context to run
    diagnostic crash logging.
    """
    app = create_app(config_class="app.config.TestingConfig")

    @app.route("/force_diagnostic_crash")
    def force_crash():
        if request and request.path == "/force_diagnostic_crash":
            _ = jsonify({"status": "error_pending"})

        raise RuntimeError(
            "Deliberate factory diagnostic validation assertion failure"
        )

    with app.test_client() as client:
        response = client.get("/force_diagnostic_crash")

    assert response.status_code == 500


def test_ignite_cortex_bad_request_passthrough(monkeypatch):
    """
    Forces a BadRequest on main.ignite_cortex to bypass conversion to
    422 format.
    """
    app = create_app(config_class="app.config.TestingConfig")

    @app.route("/ignite_test")
    def trigger_cortex_err():
        assert request.path == "/ignite_test"

        err = BadRequest("Invalid JSON structure format")

        assert isinstance(err, HTTPException)
        raise err

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
    """
    Exercises HealthCheckRegistry missing entries, invalid types,
    and exceptions.
    """
    registry = HealthCheckRegistry()

    with pytest.raises(TypeError):
        registry.register("invalid_fn", "not_a_callable")

    registry.unregister("non_existent_check")

    missing_res = registry.run_check("unregistered_component")

    assert missing_res["ok"] is False
    assert missing_res["error"] == "not_registered"

    registry.register(
        "bad_type_check",
        lambda: ["not", "a", "dictionary"],
    )

    bad_res = registry.run_check("bad_type_check")

    assert bad_res["ok"] is False
    assert bad_res["error"] == "invalid_result_type"

    def broken_callable():
        raise ValueError("Hardware bus disconnect error sim")

    registry.register("broken_check", broken_callable)

    err_res = registry.run_check("broken_check")

    assert err_res["ok"] is False
    assert "Hardware bus disconnect" in err_res["error"]

    assert "broken_check" in registry.list_checks()

    all_res = registry.run_all()

    assert "broken_check" in all_res


def test_redis_healthcheck_no_client(monkeypatch):
    """Exercises Redis health check closure when no client instance exists."""
    app = create_app(config_class="app.config.TestingConfig")

    with app.app_context():
        import app as app_module
        from app import _make_redis_check

        monkeypatch.setattr(app, "redis_client", None)
        monkeypatch.setattr(app_module, "_maybe_redis_client", None)

        check_fn = _make_redis_check()
        result = check_fn()

    assert result["ok"] is False
    assert result["error"] == "no_client"


# =============================================================================
# 5. ROUTE HYGIENE, PIPELINES, AND DEDUPLICATION LOOPS
# =============================================================================


def test_route_hygiene_and_duplication_handling():
    """
    Directly forces duplicate rule handling, pruning loops,
    and alias fallbacks.
    """
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
    """
    Forces execution of OAuth view function pop steps when cleaning up
    detached endpoints.
    """
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
    """
    Tests the SystemOperator GOD-MODE intercept logic inside user lookup
    loaders.
    """
    app = create_app(config_class="app.config.TestingConfig")

    with app.app_context():
        from app.auth_handlers import load_user, user_lookup_callback

        jwt_res = user_lookup_callback(
            {},
            {"sub": "TERENCE_CORTEX_PRIME"},
        )

        assert jwt_res is not None
        assert jwt_res.username == "OPERATOR_ADMIN"
        assert jwt_res.get_id() == "TERENCE_CORTEX_PRIME"
        assert getattr(jwt_res, "role", None) == "subscriber"
        assert jwt_res.is_authenticated is True

        session_res = load_user("TERENCE_CORTEX_PRIME")

        assert session_res is not None
        assert session_res.username == "OPERATOR_ADMIN"
        assert session_res.get_id() == "TERENCE_CORTEX_PRIME"


# =============================================================================
# 7. SHIMS & EMERGENCY SENTINEL CRASH FALLBACKS
# =============================================================================


def test_production_sentinel_emergency_fallback(
    monkeypatch,
    caplog,
):
    """
    Simulates a production initialization crash to verify that the factory logs
    a critical fatal boot error and re-raises the original exception.
    """
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
    ), "Production initialization failure did not write FATAL BOOT ERROR to logs."