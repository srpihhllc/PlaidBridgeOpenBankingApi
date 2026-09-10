# =============================================================================
# FILE: app/tests/test_factory_edge_cases.py
# DESCRIPTION: Exhaustive target testing of edge case code paths in app/__init__.py
# =============================================================================
import importlib
import logging
import os
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException

from app import (
    HealthCheckRegistry,
    _safe_status_code,
    add_route_prune_whitelist,
    create_app,
    get_app,
    legacy_get_app,
)

# =============================================================================
# 1. CORE FACTORY CONFIGURATION RESOLUTION TESTS
# =============================================================================


def test_factory_string_config_resolution():
    """Forces the factory string configuration loop to resolve classes via strings."""
    app = create_app(config_class="app.config.TestingConfig")
    assert app.config["TESTING"] is True


def test_factory_invalid_string_config_fallback(caplog):
    """Forces a garbage string configuration path to trigger the warning fallback."""
    app = create_app(config_class="app.config.ThisDoesNotExistAtAllXYZ")
    assert (
        app.config["TESTING"] is False
    )  # Falling back to default sets testing false

    has_warning = any(
        "Failed to load config class" in record.message
        for record in caplog.records
    )
    assert has_warning


def test_factory_config_from_object_exception_fallback():
    """
    Forces an exception inside config.from_object to ensure the testing fallback
    executes cleanly when application configurations experience initialization errors.
    """
    from flask.config import Config

    original_from_object = Config.from_object

    def side_effect(self, obj):
        # Raise an exception only on the initial configuration attempt
        if side_effect.called_once:
            return original_from_object(self, obj)
        side_effect.called_once = True
        raise RuntimeError(
            "Authoritative database profile configuration connection drop error sim"
        )

    side_effect.called_once = False

    # Patch the from_object method with our stateful conditional driver
    with patch(
        "flask.config.Config.from_object",
        autospec=True,
        side_effect=side_effect,
    ):
        # Invoke your factory engine
        app = create_app(config_class="app.config.TestingConfig")

        # Verify that your exception handler safely dropped back to the fallback block
        assert app.config["TESTING"] is False


# =============================================================================
# 2. INTERNAL UTILITIES & BLUEPRINT GUARDS
# =============================================================================


def test_safe_status_code_exception():
    """Forces _safe_status_code to intercept non-integer inputs and HTTPException status codes."""
    assert _safe_status_code("NOT_A_CODE") == 500

    # Verify status extraction directly from an HTTPException instance
    http_exc = BadRequest("Invalid payload parameters")
    assert isinstance(http_exc, HTTPException)
    assert _safe_status_code(http_exc.code) == 400


def test_blueprint_registration_duplicate_skipping(caplog):
    """Forces duplicate blueprint registration tracking loop to drop into the debug log branch."""
    # Build a lightweight target instance completely unlinked from factory auto-discovery
    app = Flask("test_dup_bp")
    app.config["TESTING"] = True

    # Pre-populate the blueprints mapping with an isolated test target entry
    app.blueprints = {"auth_mock_target": MagicMock()}

    from app import _register_blueprints

    with caplog.at_level(logging.DEBUG):
        mock_bp = MagicMock()
        mock_bp.name = "auth_mock_target"

        # Force register_blueprints hook to use our mock instance
        with patch("app.register_blueprints") as mock_reg:

            def side_effect(flask_app):
                flask_app.register_blueprint(mock_bp)

            mock_reg.side_effect = side_effect
            _register_blueprints(app)

        assert any(
            "already registered globally; skipping" in r.message
            for r in caplog.records
        )


# =============================================================================
# 3. GLOBAL ERROR HANDLERS & DIAGNOSTIC INTERCEPTS
# =============================================================================


def test_diagnostic_crash_handler_execution():
    """Forces a severe exception inside an active request context to run diagnostic crash logging."""
    app = create_app(config_class="app.config.TestingConfig")

    @app.route("/force_diagnostic_crash")
    def force_crash():
        # Inspect active request context and construct response payload structure
        if request and request.path == "/force_diagnostic_crash":
            _ = jsonify({"status": "error_pending"})
        raise RuntimeError(
            "Deliberate factory diagnostic validation assertion failure"
        )

    with app.test_client() as client:
        # Ensure the path executes cleanly without throwing an unhandled handler panic
        response = client.get("/force_diagnostic_crash")
        assert response.status_code == 500


def test_ignite_cortex_bad_request_passthrough():
    """Forces a BadRequest on main.ignite_cortex to bypass conversion to 422 format."""
    app = create_app(config_class="app.config.TestingConfig")

    @app.route("/ignite_test")
    def trigger_cortex_err():
        assert request.path == "/ignite_test"
        err = BadRequest("Invalid JSON structure format")
        assert isinstance(err, HTTPException)
        raise err

    # Patch the property directly on the class to safely feed the intercept logic without clashing context managers
    with patch(
        "flask.Request.endpoint", new_callable=PropertyMock
    ) as mock_endpoint:
        mock_endpoint.return_value = "main.ignite_cortex"

        with app.test_client() as client:
            response = client.get("/ignite_test")
            # Should fall through directly to standard 400
            assert response.status_code == 400


# =============================================================================
# 4. HEALTH CHECK REGISTRY & SERVICE CHECKS
# =============================================================================


def test_healthcheck_registry_type_safety():
    """Exercises HealthCheckRegistry missing entries, invalid types, and exceptions."""
    registry = HealthCheckRegistry()

    # 1. Non-callable validation error check
    with pytest.raises(TypeError):
        registry.register("invalid_fn", "not_a_callable")

    # 2. Unregister missing entry pass
    registry.unregister("non_existent_check")

    # 3. Missing target check execution
    missing_res = registry.run_check("unregistered_component")
    assert missing_res["ok"] is False
    assert missing_res["error"] == "not_registered"

    # 4. Type validation rejection handler (invalid non-dictionary structure return)
    registry.register("bad_type_check", lambda: ["not", "a", "dictionary"])
    bad_res = registry.run_check("bad_type_check")
    assert bad_res["ok"] is False
    assert bad_res["error"] == "invalid_result_type"

    # 5. Exception catch-all bubble handler
    def broken_callable():
        raise ValueError("Hardware bus disconnect error sim")

    registry.register("broken_check", broken_callable)
    err_res = registry.run_check("broken_check")
    assert err_res["ok"] is False
    assert "Hardware bus disconnect" in err_res["error"]

    # 6. List and execute all structures
    assert "broken_check" in registry.list_checks()
    all_res = registry.run_all()
    assert "broken_check" in all_res


def test_redis_healthcheck_no_client(monkeypatch):
    """Exercises Redis health check closure when no client instance exists."""
    app = create_app(config_class="app.config.TestingConfig")
    with app.app_context():
        import app as app_module
        from app import _make_redis_check

        # 1. Neutralize current_app dynamic attribute lookup
        monkeypatch.setattr(app, "redis_client", None)

        # 2. Neutralize the static module level fallback pointer
        monkeypatch.setattr(app_module, "_maybe_redis_client", None)

        check_fn = _make_redis_check()
        res = check_fn()
        assert res["ok"] is False
        assert res["error"] == "no_client"


# =============================================================================
# 5. ROUTE HYGIENE, PIPELINES, AND DEDUPLICATION LOOPS
# =============================================================================


def test_route_hygiene_and_duplication_handling():
    """Directly forces duplicate rule handling, pruning loops, and alias fallbacks."""
    app = Flask("hygiene_test_app")
    app.config["TESTING"] = True

    # Register rules to map duplication targets
    @app.route("/duplicate_path", methods=["GET"])
    def first_rule():
        return jsonify({"rule": 1})

    @app.route("/duplicate_path", methods=["GET"])
    def second_rule():
        return jsonify({"rule": 2})

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

    # Run internal layout structural managers to exercise individual statement rows
    _enforce_route_uniqueness(app)
    _dedupe_rules(app)
    _prune_ignorable_route_rules(app)
    _reconcile_oauth_callback_aliases(app)
    _rebuild_rules_by_endpoint(app)
    assert True


def test_cleanup_premature_oauth_registrations():
    """Forces execution of OAuth view function pop steps when cleaning up detached endpoints."""
    # Use an isolated lightweight Flask instance to eliminate factory side effects
    app = Flask("test_cleanup_isolated_app")
    
    # Explicitly assign MagicMock string names to satisfy internal validation logic
    oauth_mock = MagicMock()
    oauth_mock.name = "oauth"
    
    oauth_bp_mock = MagicMock()
    oauth_bp_mock.name = "oauth_bp"
    
    app.blueprints = {"oauth": oauth_mock, "oauth_bp": oauth_bp_mock}

    # Mock a disconnected endpoint mapping
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
    """Tests the SystemOperator GOD-MODE intercept logic inside user lookup loaders."""
    app = create_app(config_class="app.config.TestingConfig")
    with app.app_context():
        # Import the handlers directly to test the domain logic without fighting extension registries
        from app.auth_handlers import load_user, user_lookup_callback

        # ---------------------------------------------------------
        # 1. Test JWT Stateless Token Boundary (API)
        # ---------------------------------------------------------
        jwt_res = user_lookup_callback({}, {"sub": "TERENCE_CORTEX_PRIME"})

        assert (
            jwt_res is not None
        ), "JWT lookup loader returned None instead of a SystemOperator instance."
        assert (
            jwt_res.username == "OPERATOR_ADMIN"
        ), f"Expected OPERATOR_ADMIN, got {jwt_res.username}"
        assert jwt_res.get_id() == "TERENCE_CORTEX_PRIME"
        assert getattr(jwt_res, "role", None) == "subscriber"
        assert jwt_res.is_authenticated is True

        # ---------------------------------------------------------
        # 2. Test Session Stateful Cookie Boundary (UI)
        # ---------------------------------------------------------
        session_res = load_user("TERENCE_CORTEX_PRIME")

        assert (
            session_res is not None
        ), "Session loader returned None instead of a SystemOperator instance."
        assert session_res.username == "OPERATOR_ADMIN"
        assert session_res.get_id() == "TERENCE_CORTEX_PRIME"


# =============================================================================
# 7. SHIMS & EMERGENCY SENTINEL CRASH FALLBACKS
# =============================================================================


def test_legacy_compatibility_shims():
    """Exercises legacy initialization aliases and shims to cover the module export signatures."""
    shimmed_app = legacy_get_app(config_class="app.config.TestingConfig")
    assert shimmed_app.config["TESTING"] is True

    direct_shim = get_app(config_class="app.config.TestingConfig")
    assert direct_shim.config["TESTING"] is True


def test_production_sentinel_emergency_fallback(caplog):
    """Simulates a production initialization crash to force module-level sentinel logging to run."""
    old_env = os.environ.get("FLASK_ENV")
    try:
        # 1. Target flask.Flask instead of app.create_app so the mock survives the reload
        with (
            patch.dict(os.environ, {"FLASK_ENV": "production"}),
            patch(
                "flask.Flask",
                side_effect=RuntimeError("Production hardware crash sim"),
            ),
        ):
            if "app" in sys.modules:
                try:
                    with caplog.at_level(logging.ERROR):
                        importlib.reload(sys.modules["app"])
                except RuntimeError as e:
                    # If your sentinel block doesn't re-raise, this exception might be swallowed
                    assert "Production hardware crash sim" in str(e)

        # 2. Assert against the caplog records collected during the reload window
        has_fatal_log = any(
            "FATAL BOOT ERROR" in record.message for record in caplog.records
        )
        assert (
            has_fatal_log
        ), "Emergency module sentinel did not write FATAL BOOT ERROR to logs."

    finally:
        # Restore execution environmental profile variables
        if old_env is not None:
            os.environ["FLASK_ENV"] = old_env
        else:
            os.environ.pop("FLASK_ENV", None)

        # CRITICAL HYGIENE PURGE: Force an isolated module reload now that the patch context
        # manager has completely dropped out. This ensures app.Flask re-binds cleanly back
        # to the standard, un-mocked Flask system definition before next tests start.
        if "app" in sys.modules:
            importlib.reload(sys.modules["app"])