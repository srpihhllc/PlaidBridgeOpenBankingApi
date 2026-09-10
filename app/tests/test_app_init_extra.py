# app/tests/test_app_init_extra.py

from unittest.mock import MagicMock, patch

from flask import Flask

from app import (
    _build_dependency_graph,
    _cleanup_premature_oauth_registrations,
    _ensure_db_tables,
    _gather_diagnostics,
    _rebuild_rules_by_endpoint,
    _register_core_routes,
)


def test_error_handler_crash_dump_fallbacks():
    app = Flask(__name__)
    app.config.update(
        TESTING=False,
        DEBUG=False,
        ENV="production",
    )

    from app import _register_error_handlers

    with patch("builtins.open", side_effect=Exception("fail_open")):
        _register_error_handlers(app)

        @app.route("/boom")
        def boom():
            raise Exception("crash")

        with app.test_client() as client:
            response = client.get("/boom")

    assert response.status_code == 500
    assert response.get_json()["msg"] == "Internal Server Error"


def test_ensure_db_tables_skips_when_alembic_running(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = False
    monkeypatch.setenv("ALEMBIC_RUNNING", "1")

    with patch("app.db.create_all") as mock_create:
        _ensure_db_tables(app)

    mock_create.assert_not_called()


def test_ensure_db_tables_logs_failure_non_testing(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = False
    monkeypatch.delenv("ALEMBIC_RUNNING", raising=False)

    with patch("app.db.create_all", side_effect=Exception("db_fail")):
        with patch("app._logger.exception") as mock_log:
            _ensure_db_tables(app)

    mock_log.assert_called()


def test_healthcheck_unregister_calls_registry():
    from app import _registry, unregister_healthcheck

    def healthcheck():
        return {"ok": True}

    _registry.register("x", healthcheck)
    unregister_healthcheck("x")

    assert "x" not in _registry.list_checks()


def test_migrations_check_query_failure():
    from app import _make_migrations_check, create_app, db

    app = create_app()

    app.config.update(
        TESTING=True,
        DEBUG=False,
    )

    with app.app_context():
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["alembic_version"]

        with patch("app.inspect", return_value=inspector):
            with patch.object(
                db.session,
                "execute",
                side_effect=Exception("query_fail"),
            ):
                check = _make_migrations_check()
                result = check()

    assert result["ok"] is False
    assert "query_fail" in result["error"]


def test_gather_diagnostics_success():
    app = Flask(__name__)

    with patch(
        "app.diagnostics.gather_diagnostics",
        return_value={"ok": True},
    ) as mock_gather:
        result = _gather_diagnostics(app)

    assert result == {"ok": True}
    mock_gather.assert_called_once()


def test_dependency_graph_success():
    app = Flask(__name__)

    with patch(
        "app.diagnostics.build_dependency_graph",
        return_value={"nodes": ["a"]},
    ) as mock_build:
        result = _build_dependency_graph(app)

    assert result == {"nodes": ["a"]}
    mock_build.assert_called_once()


def test_version_route_includes_git_sha():
    app = Flask(__name__)
    app.config["GIT_SHA"] = "abc123"

    _register_core_routes(app)

    with app.test_client() as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.get_json()["git_sha"] == "abc123"


def test_register_core_routes_failure_logs_debug():
    app = Flask(__name__)

    with patch(
        "app._build_dependency_graph",
        side_effect=Exception("fail"),
    ):
        with patch("app._logger.debug") as mock_debug:
            _register_core_routes(app)

    mock_debug.assert_called()


def test_rebuild_rules_by_endpoint_rebuilds_map():
    app = Flask(__name__)

    @app.route("/x")
    def x():
        return "ok"

    _rebuild_rules_by_endpoint(app)

    rules_by_endpoint = getattr(app.url_map, "_rules_by_endpoint")

    assert "x" in rules_by_endpoint
    assert len(rules_by_endpoint["x"]) == 1


def test_cleanup_premature_oauth_registrations():
    app = Flask(__name__)

    def fake_view():
        return "ok"

    fake_view.__module__ = "app.blueprints.oauth_routes.something"
    app.view_functions["oauth.bad"] = fake_view

    class FakeRule:
        endpoint = "oauth.bad"

    app.url_map.iter_rules = lambda: [FakeRule()]

    with patch("app._logger.debug") as mock_debug:
        _cleanup_premature_oauth_registrations(app)

    assert "oauth.bad" not in app.view_functions
    mock_debug.assert_called()
