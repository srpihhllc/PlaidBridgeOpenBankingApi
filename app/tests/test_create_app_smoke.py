# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_create_app_smoke.py

import pytest
from flask import abort
from flask.config import Config

from app import (
    _cleanup_premature_oauth_registrations,
    _dedupe_rules,
    _enforce_route_uniqueness,
    _make_db_check,
    _make_redis_check,
    _prune_ignorable_route_rules,
    _reconcile_oauth_callback_aliases,
    _registry,
    add_route_prune_whitelist,
    create_app,
)
from app.config import DevelopmentConfig, ProductionConfig, TestingConfig
from app.extensions import db


def test_create_app_and_basic_endpoints():
    """Verify application factory instantiation and health endpoints."""
    app = create_app(config_class=TestingConfig)
    assert app.config.get("TESTING") is True

    rules = {rule.rule for rule in app.url_map.iter_rules()}
    health_routes = {
        "/pulse/health",
        "/api/v1/health",
        "/diagnostics/health",
        "/healthz",
        "/health",
    }
    active_health_routes = rules.intersection(health_routes)
    assert active_health_routes, (
        f"No health routes found in registered rules: {rules}"
    )

    client = app.test_client()
    for route in active_health_routes:
        response = client.get(route)
        assert response.status_code in (200, 503)


def test_create_app_with_dev_and_prod_configs(monkeypatch):
    """Assert initialization integrity across target runtime environments."""
    monkeypatch.setenv("SECRET_KEY", "smoketest-super-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", "smoketest-jwt-secret")
    monkeypatch.setenv("DB_USER", "smoketest_user")
    monkeypatch.setenv("DB_PASSWORD", "smoketest_pass")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "smoketest_db")
    from cryptography.fernet import Fernet
    monkeypatch.setenv("PII_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("PLAID_ENCRYPTION_KEY", Fernet.generate_key().decode())

    dev_app = create_app(config_class=DevelopmentConfig)
    assert dev_app.config.get("TESTING") is False

    prod_app = create_app(config_class=ProductionConfig)
    assert prod_app.config.get("TESTING") is False


def test_create_app_with_invalid_config_class(monkeypatch):
    """Verify config-loading errors propagate instead of creating a fallback app."""
    # Ensure production values in a developer's .env do not override this test.
    monkeypatch.setenv("ENV_NAME", "testing")
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("FLASK_CONFIG", "testing")

    def mock_from_object(self, obj):
        raise ValueError("Simulated internal config iteration failure")

    monkeypatch.setattr(Config, "from_object", mock_from_object)

    with pytest.raises(
        ValueError,
        match="Simulated internal config iteration failure",
    ):
        create_app(config_class=TestingConfig)


def test_global_error_handlers_execution():
    """Verify application-wide exception handling and response codes."""
    app = create_app(config_class=TestingConfig)

    @app.route("/_test_500_error")
    def trigger_500():
        abort(500)

    @app.route("/_test_400_error")
    def trigger_400():
        abort(400)

    client = app.test_client()

    assert client.get("/completely-invalid-system-route-404").status_code == 404
    assert client.get("/_test_500_error").status_code == 500
    assert client.get("/_test_400_error").status_code in (400, 422)


def test_healthcheck_registry_edge_cases():
    """Exercise registry behavior for missing and malformed checks."""
    missing_result = _registry.run_check("completely_fictitional_metric_key")
    assert missing_result["ok"] is False
    assert missing_result["error"] == "not_registered"

    _registry.register("bad_type_check", lambda: "not-a-dictionary")
    try:
        bad_result = _registry.run_check("bad_type_check")
        assert bad_result["ok"] is False
        assert bad_result["error"] == "invalid_result_type"
    finally:
        _registry.unregister("bad_type_check")


def test_healthcheck_failures_and_missing_backends(monkeypatch):
    """Exercise health checks when Redis or database access fails."""
    app = create_app(config_class=TestingConfig)

    with app.app_context():
        monkeypatch.setattr(app, "redis_client", None)
        redis_checker = _make_redis_check()
        redis_result = redis_checker()
        assert redis_result["ok"] is False
        assert redis_result["error"] == "no_client"

        def mock_execute_fail(*args, **kwargs):
            raise Exception("Simulated DB Connection Failure")

        monkeypatch.setattr(db.session, "execute", mock_execute_fail)
        db_checker = _make_db_check()
        db_result = db_checker()
        assert db_result["ok"] is False
        assert "Simulated DB Connection Failure" in db_result["error"]


def test_route_hygiene_and_pruning_passes():
    """Exercise route pruning, uniqueness, and aliasing passes."""

    class AdminForcedConfig(TestingConfig):
        ADMIN_UI_ENABLED = True
        FORCE_REGISTER_ADMIN_UI_IN_TESTS = True

    app = create_app(config_class=AdminForcedConfig)

    current_len = len(add_route_prune_whitelist("forced_test_whitelist_item"))
    assert current_len > 0

    @app.route("/_tmp/test_prune", endpoint="tmp_prune_target")
    def dummy_prune_one():
        return "prune"

    with app.app_context():
        _cleanup_premature_oauth_registrations(app)
        _prune_ignorable_route_rules(app)
        _reconcile_oauth_callback_aliases(app)
        _enforce_route_uniqueness(app)
        _dedupe_rules(app)


@pytest.mark.parametrize(
    "route",
    ["/readyz", "/version", "/diagnostics", "/dependency_graph", "/metrics"],
)
def test_core_telemetry_routes(route):
    """Verify foundational telemetry routes return safely."""
    app = create_app(config_class=TestingConfig)
    response = app.test_client().get(route)
    assert response.status_code in (200, 503)
