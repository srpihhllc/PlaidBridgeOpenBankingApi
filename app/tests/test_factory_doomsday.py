# =============================================================================
# FILE: app/tests/test_factory_doomsday.py
# DESCRIPTION: "Doomsday" coverage suite. Injects poisoned objects and
#              simulates catastrophic dependency failures.
# =============================================================================

import logging

import pytest
from flask import Flask

import app as app_module


def mock_raise(*args, **kwargs):
    """Generic function to force a system exception."""
    raise RuntimeError("Simulated catastrophic failure")


def test_safe_status_code_exception():
    """Forces _safe_status_code to hit its exception block."""

    class Uncastable:
        def __int__(self):
            raise ValueError("Cannot cast")

    assert app_module._safe_status_code(Uncastable()) == 500


def test_register_blueprints_catastrophic_failure(monkeypatch):
    """Forces the outer try/except block in blueprint auto-discovery to fail."""
    app = Flask(__name__)
    monkeypatch.setattr(app, "register_blueprint", mock_raise)
    with pytest.raises(RuntimeError):
        app_module._register_blueprints(app)


def test_ensure_db_tables_exceptions(monkeypatch):
    """Simulates SQLAlchemy creation and inspection failures."""
    app = Flask(__name__)

    # 1. TESTING = True branch failure
    app.config["TESTING"] = True
    monkeypatch.setattr(app_module.db, "create_all", mock_raise)
    app_module._ensure_db_tables(app)

    # 2. TESTING = False branch failure (Inspection crash)
    app.config["TESTING"] = False
    monkeypatch.setattr(app_module, "inspect", mock_raise)
    app_module._ensure_db_tables(app)


def test_healthcheck_factory_exceptions(monkeypatch):
    """Forces inner try/except blocks inside healthcheck execution generators."""
    # Force Database check failure
    db_check = app_module._make_db_check()
    monkeypatch.setattr(app_module.db.session, "execute", mock_raise)
    assert db_check()["ok"] is False

    # Force Redis check failure (Simulate broken ping property)
    class BrokenRedis:
        @property
        def ping(self):
            raise RuntimeError("Redis connection dropped")

    app = Flask(__name__)
    app.redis_client = BrokenRedis()
    with app.app_context():
        redis_check = app_module._make_redis_check()
        assert redis_check()["ok"] is False

    # Force Migrations check failure
    mig_check = app_module._make_migrations_check()
    monkeypatch.setattr(app_module, "inspect", mock_raise)
    assert mig_check()["ok"] is False


def test_correlation_id_filter_header_exception(monkeypatch):
    """Breaks the request object to force fallback UUID generation in the logger filter."""

    class BrokenRequest:
        @property
        def headers(self):
            raise RuntimeError("Headers inaccessible")

    monkeypatch.setattr(app_module, "request", BrokenRequest())

    log_filter = app_module.CorrelationIdFilter()

    class DummyRecord:
        pass

    record = DummyRecord()
    log_filter.filter(record)
    assert record.correlation_id is not None
    assert record.correlation_id.startswith("cid-")


def test_diagnostic_and_graph_import_failures(monkeypatch):
    """Forces module import failures to trigger diagnostic fallbacks."""
    monkeypatch.setattr("importlib.import_module", mock_raise)
    app = Flask(__name__)

    diag = app_module._gather_diagnostics(app)
    assert "minimal diagnostics fallback" in diag["notes"]

    graph = app_module._build_dependency_graph(app)
    assert graph["dot"] == "digraph {}"


def test_hygiene_functions_catastrophic_failures():
    """
    Passes a poisoned Flask app object to route hygiene functions
    to trigger their outermost except Exception layers.
    """

    class ExplodingApp:
        @property
        def view_functions(self):
            raise RuntimeError("Boom")

        @property
        def url_map(self):
            raise RuntimeError("Boom")

        @property
        def blueprints(self):
            raise RuntimeError("Boom")

        @property
        def logger(self):
            return logging.getLogger("dummy")

    poisoned_app = ExplodingApp()

    app_module._cleanup_premature_oauth_registrations(poisoned_app)
    app_module._prune_ignorable_route_rules(poisoned_app)
    app_module._reconcile_oauth_callback_aliases(poisoned_app)
    app_module._enforce_route_uniqueness(poisoned_app)
    app_module._dedupe_rules(poisoned_app)
    app_module._stabilize_rules_order(poisoned_app)
    app_module._rebuild_rules_by_endpoint(poisoned_app)

    admin_func = getattr(
        app_module,
        "ensure_admin_aliases",
        getattr(app_module, "_ensure_admin_index_registered", None),
    )
    if admin_func:
        try:
            admin_func(poisoned_app)
        except Exception:
            pass