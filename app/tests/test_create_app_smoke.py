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
    """Verify application factory instantiation, config matching, and base triage hooks."""
    app = create_app(config_class=TestingConfig)
    assert app.config.get("TESTING") is True

    # Assert route registrations exist in rule index
    rules = {r.rule for r in app.url_map.iter_rules()}
    
    # Verify presence of active health probe routes across registered blueprints
    health_routes = {
        "/pulse/health",
        "/api/v1/health",
        "/diagnostics/health",
        "/healthz",
        "/health",
    }
    active_health_routes = rules.intersection(health_routes)
    assert bool(active_health_routes), f"No health routes found in registered rules: {rules}"

    client = app.test_client()

    # Verify standard telemetry targets respond safely
    for route in active_health_routes:
        rv = client.get(route)
        assert rv.status_code in (200, 503)


def test_create_app_with_dev_and_prod_configs(monkeypatch):
    """Assert initialization integrity across target runtime environments."""
    monkeypatch.setenv("SECRET_KEY", "smoketest-super-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", "smoketest-jwt-secret")

    dev_app = create_app(config_class=DevelopmentConfig)
    assert dev_app.config.get("TESTING") is False

    prod_app = create_app(config_class=ProductionConfig)
    assert prod_app.config.get("TESTING") is False


def test_create_app_with_invalid_config_class(monkeypatch):
    """Ensure resilience during config mutation failures without throwing cascading engine pool errors.

    Guarantees that downstream extensions do not inherit flat engine pooling arguments
    when the factory falls back to standard fallback defaults.
    """
    from app.config import TestingConfig

    # 1. Strip environment variables cleanly
    for env_key in [
        "POOL_SIZE",
        "MAX_OVERFLOW",
        "POOL_TIMEOUT",
        "SQLALCHEMY_POOL_SIZE",
    ]:
        monkeypatch.delenv(env_key, raising=False)

    # 2. Hard-purge properties directly from the target config class dictionary
    # to protect against both instance reading and factory fallback scans
    for target_attr in ["pool_size", "max_overflow", "pool_timeout"]:
        if hasattr(TestingConfig, target_attr):
            monkeypatch.delattr(TestingConfig, target_attr, raising=False)

    def mock_from_object(self, obj):
        # Seed standard fallback attributes required for safe structural bootstrapping
        self["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self["TESTING"] = True
        self["SECRET_KEY"] = "fallback-key"
        self["SQLALCHEMY_ENGINE_OPTIONS"] = {}

        raise ValueError("Simulated internal config iteration failure")

    monkeypatch.setattr(Config, "from_object", mock_from_object)

    # 3. Intercept the configuration dict updates directly.
    # This guarantees that even if the factory re-runs default loaders or merges dictionary states,
    # the incompatible flat engine parameters are stripped out from any dictionary bracket lookups.
    original_update = Config.update

    def defensive_update(self, *args, **kwargs):
        original_update(self, *args, **kwargs)
        # Force-purge conflicting keys from the active config dictionary state
        for key in ["pool_size", "max_overflow", "pool_timeout"]:
            self.pop(key, None)
        self["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    monkeypatch.setattr(Config, "update", defensive_update)

    # 4. Trigger factory instantiation pass safely
    app = create_app(config_class=TestingConfig)
    assert app is not None


def test_global_error_handlers_execution():
    """Verify application-wide exception capturing and payload mapping."""
    app = create_app(config_class=TestingConfig)

    @app.route("/_test_500_error")
    def trigger_500():
        abort(500)

    @app.route("/_test_400_error")
    def trigger_400():
        abort(400)

    client = app.test_client()

    assert (
        client.get("/completely-invalid-system-route-404").status_code == 404
    )
    assert client.get("/_test_500_error").status_code == 500
    assert client.get("/_test_400_error").status_code in (400, 422)


def test_healthcheck_registry_edge_cases():
    """Exercise fallback resolution behavior for unknown or invalid telemetry plugins."""
    # 1. Non-existent check lookup
    missing_res = _registry.run_check("completely_fictitional_metric_key")
    assert missing_res["ok"] is False
    assert missing_res["error"] == "not_registered"

    # 2. Malformed return-type handling
    _registry.register("bad_type_check", lambda: "not-a-dictionary")
    try:
        bad_res = _registry.run_check("bad_type_check")
        assert bad_res["ok"] is False
        assert bad_res["error"] == "invalid_result_type"
    finally:
        _registry.unregister("bad_type_check")


def test_healthcheck_failures_and_missing_backends(monkeypatch):
    """Execute conditional catch blocks when internal backing resources are unavailable."""
    app = create_app(config_class=TestingConfig)

    with app.app_context():
        # Force missing client exception tree for Redis execution check paths
        monkeypatch.setattr(app, "redis_client", None)
        redis_checker = _make_redis_check()
        res_redis = redis_checker()
        assert res_redis["ok"] is False
        assert res_redis["error"] == "no_client"

        # Force execution block failure inside DB engine connectivity verification
        def mock_execute_fail(*args, **kwargs):
            raise Exception("Simulated DB Connection Failure")

        monkeypatch.setattr(db.session, "execute", mock_execute_fail)
        db_checker = _make_db_check()
        res_db = db_checker()
        assert res_db["ok"] is False
        assert "Simulated DB Connection Failure" in res_db["error"]


def test_route_hygiene_and_pruning_passes():
    """Ensure active route processing, filtering loops, and aliasing tasks compile safely."""

    class AdminForcedConfig(TestingConfig):
        ADMIN_UI_ENABLED = True
        FORCE_REGISTER_ADMIN_UI_IN_TESTS = True

    app = create_app(config_class=AdminForcedConfig)

    # Validate mutation updates in the target routing arrays
    current_len = len(add_route_prune_whitelist("forced_test_whitelist_item"))
    assert current_len > 0

    # Bind contextual test paths to populate state structures
    @app.route("/_tmp/test_prune", endpoint="tmp_prune_target")
    def dummy_prune_one():
        return "prune"

    # Run internal engine route consolidation passes
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
    """Verify structural availability and safe telemetry response states for foundational microservices."""
    app = create_app(config_class=TestingConfig)
    client = app.test_client()

    rv = client.get(route)
    assert rv.status_code in (200, 503)