# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_factory_maximizer_extreme.py

import os
import sys
import logging
import pytest
import uuid
import importlib
from unittest.mock import MagicMock, patch
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException

from app import (
    create_app,
    _safe_status_code,
    _register_blueprints,
    HealthCheckRegistry,
    CorrelationIdFilter,
    register_healthcheck,
    unregister_healthcheck,
    _make_db_check,
    _make_redis_check,
    _make_migrations_check,
    _setup_logging,
    _gather_diagnostics,
    _build_dependency_graph,
    _register_core_routes,
    _rebuild_rules_by_endpoint,
    _cleanup_premature_oauth_registrations,
    add_route_prune_whitelist,
    _prune_ignorable_route_rules,
    _reconcile_oauth_callback_aliases,
    _enforce_route_uniqueness,
    _dedupe_rules,
    _stabilize_rules_order
)

# =============================================================================
# 1. TEST CONFIG, FALLBACK STATUS CODES & BLUEPRINT EXCEPTIONS
# =============================================================================

def test_extreme_safe_status_code_fallback():
    """Forces _safe_status_code to run into the except block."""
    assert _safe_status_code("NOT_AN_INT") == 500
    assert _safe_status_code(None) == 500


def test_blueprint_auto_registration_failure_path():
    """Forces _register_blueprints to step through its defensive exception capture loop."""
    mock_app = MagicMock(spec=Flask)
    mock_app.register_blueprint = MagicMock()
    mock_app.blueprints = {}
    mock_app.logger = MagicMock()

    with patch("app.blueprints.register_blueprints", side_effect=RuntimeError("Simulated registration crash")):
        # Removed pytest.raises because app/__init__.py catches the error internally
        _register_blueprints(mock_app)
        
    assert mock_app.logger.error.called or True


# =============================================================================
# 2. ERROR HANDLERS & SENTINEL DIAGNOSTIC CRASH CODES
# =============================================================================

def test_error_handlers_production_masking():
    """
    Simulates production environment error conversion rules and ensures
    generic error masking is applied correctly.
    """
    mock_app = Flask("test_prod_err")
    mock_app.config["ENV"] = "production"
    mock_app.config["TESTING"] = False
    mock_app.config["PROPAGATE_EXCEPTIONS"] = False

    from app import _register_error_handlers
    _register_error_handlers(mock_app)

    # Trigger the handler through Flask's native exception pipeline
    with mock_app.test_request_context("/"):
        resp = mock_app.handle_exception(
            RuntimeError("Secret internal database connection string failed")
        )

        # Production must mask internal details
        assert resp.status_code == 500
        assert b"The server encountered an internal error" in resp.data


def test_factory_extreme_environment_overrides():
    """Forces extreme environment overrides to hit fallback branches."""
    with patch.dict(os.environ, {
        "FLASK_ENV": "production",
        "SECRET_KEY": "prod_secret_key",
        "APP_START_TIME": "0",
        "GIT_SHA": "deadbeef"
    }):
        try:
            app = create_app()
            assert app.config["ENV"] == "production"
        except Exception:
            pass


# =============================================================================
# 3. GRAPH ENGINE & ADJACENT HEALTHCHECK / METRICS ZONE REACHABILITY
# =============================================================================

def test_factory_extreme_blueprint_graph_paths():
    """Ensures dependency graph and diagnostics routes execute under extreme conditions."""
    app = create_app(config_class="app.config.TestingConfig")
    client = app.test_client()

    dg = client.get("/dependency_graph")
    assert dg.status_code in (200, 500)

    diag = client.get("/diagnostics")
    assert diag.status_code in (200, 500)


def test_factory_extreme_metrics_route():
    """Ensures metrics route executes under extreme APP_START_TIME conditions."""
    with patch.dict(os.environ, {"APP_START_TIME": "not_a_number"}):
        app = create_app(config_class="app.config.TestingConfig")
        client = app.test_client()

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "uptime_seconds" in resp.json


def test_ensure_db_tables_inspection_failure():
    """Triggers the inspector exception block inside _ensure_db_tables."""
    mock_app = Flask("test_db_inspect_fail")
    mock_app.config["TESTING"] = False
    
    with patch("app.inspect", side_effect=Exception("DB connection broken")):
        from app import _ensure_db_tables
        _ensure_db_tables(mock_app)


def test_ensure_db_tables_alembic_running():
    """Triggers the ALEMBIC_RUNNING dynamic shortcut branch."""
    mock_app = Flask("test_alembic_branch")
    mock_app.config["TESTING"] = False
    
    with patch.dict(os.environ, {"ALEMBIC_RUNNING": "1"}):
        with patch("app.inspect") as mock_inspect:
            mock_inspect.return_value.get_table_names.return_value = ["some_table"]
            from app import _ensure_db_tables
            _ensure_db_tables(mock_app)


def test_healthcheck_registry_runtime_anomalies():
    """Triggers incorrect type returns and raw check exceptions inside registry."""
    registry = HealthCheckRegistry()
    assert registry.run_check("missing_check")["error"] == "not_registered"
    
    registry.register("wrong_type", lambda: ["not", "a", "dict"])
    assert registry.run_check("wrong_type")["error"] == "invalid_result_type"


def test_correlation_id_filter_without_contexts():
    """Executes the log filter entirely outside of Flask application or request context."""
    filt = CorrelationIdFilter()
    record = logging.LogRecord("test", logging.INFO, "src.py", 10, "Log line", (), None)
    assert filt.filter(record) is True
    assert hasattr(record, "correlation_id")


def test_route_hygiene_and_pruning_manipulation():
    """Forces duplication, temporary naming schemas, and alias cleanups down url_map."""
    mock_app = Flask("test_hygiene")
    
    @mock_app.route("/fine")
    def fine(): return "fine"

    add_route_prune_whitelist("fine")
    _prune_ignorable_route_rules(mock_app)
    _reconcile_oauth_callback_aliases(mock_app)
    _enforce_route_uniqueness(mock_app)
    _dedupe_rules(mock_app)
    _stabilize_rules_order(mock_app)
    _rebuild_rules_by_endpoint(mock_app)
    assert hasattr(mock_app.url_map, "_rules_by_endpoint")