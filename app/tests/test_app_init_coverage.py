# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_app_init_coverage.py

import logging
from unittest.mock import ANY, MagicMock, PropertyMock, mock_open, patch

from flask import Flask, Request
from werkzeug.exceptions import BadRequest

import app as app_module
from app import (
    ROUTE_PRUNE_WHITELIST,
    CorrelationIdFilter,
    _cleanup_premature_oauth_registrations,
    _ensure_db_tables,
    _make_migrations_check,
    _prune_ignorable_route_rules,
    _rebuild_rules_by_endpoint,
    _reconcile_oauth_callback_aliases,
    _register_core_routes,
    _register_error_handlers,
    add_route_prune_whitelist,
)


def _oauth_test_app():
    """Create an app with a mocked URL map suitable for rule mutation tests."""
    app = Flask(__name__)
    app.url_map = MagicMock()
    return app


def test_error_handler_crash_dump_partial_request_context():
    """Crash dumps should handle a partially unavailable request context."""
    app = Flask(__name__)
    _register_error_handlers(app)

    @app.route("/crash")
    def crash():
        raise RuntimeError("Simulated crash")

    file_mock = mock_open()

    with patch("builtins.open", file_mock):
        with patch.object(
            Request,
            "url",
            new=PropertyMock(
                side_effect=RuntimeError("Request URL broken"),
            ),
        ):
            response = app.test_client().get("/crash")

    assert response.status_code == 500

    handle = file_mock()
    written_content = "".join(
        call.args[0] for call in handle.write.call_args_list if call.args
    )

    assert "Request context unavailable or partial" in written_content


def test_error_handler_ignite_cortex_passthrough():
    """BadRequest from main.ignite_cortex should remain HTTP 400."""
    app = Flask(__name__)
    _register_error_handlers(app)

    @app.route("/ignite", endpoint="main.ignite_cortex")
    def ignite():
        raise BadRequest("Invalid request payload")

    response = app.test_client().get("/ignite")
    assert response.status_code == 400


def test_ensure_db_tables_schema_inspection_failure(monkeypatch):
    """Schema inspection errors should be logged and handled safely."""
    app = Flask(__name__)
    app.config["TESTING"] = False

    monkeypatch.setattr(
        app_module,
        "inspect",
        MagicMock(
            side_effect=RuntimeError(
                "Database connection timed out",
            ),
        ),
    )

    with patch.object(
        app_module._logger,
        "exception",
    ) as mock_log_exception:
        _ensure_db_tables(app)

    mock_log_exception.assert_called_once()
    assert (
        "Failed to inspect DB schema" in mock_log_exception.call_args.args[0]
    )


def test_ensure_db_tables_alembic_running(monkeypatch):
    """Database creation should be skipped during Alembic execution."""
    app = Flask(__name__)
    app.config["TESTING"] = False

    monkeypatch.setenv("ALEMBIC_RUNNING", "1")

    inspector = MagicMock()
    inspector.get_table_names.return_value = ["some_other_table"]

    monkeypatch.setattr(
        app_module,
        "inspect",
        MagicMock(return_value=inspector),
    )

    with patch.object(app_module, "db") as mock_db:
        with patch.object(
            app_module._logger,
            "debug",
        ) as mock_debug:
            _ensure_db_tables(app)

    mock_db.create_all.assert_not_called()
    mock_debug.assert_called_once_with(
        "ALEMBIC_RUNNING=1; skipping db.create_all()",
    )


def test_make_migrations_check_outer_exception(monkeypatch):
    """Migration checks should format inspection failures consistently."""
    monkeypatch.setattr(
        app_module,
        "inspect",
        MagicMock(
            side_effect=RuntimeError("Failed DB inspect"),
        ),
    )

    result = _make_migrations_check()()

    assert result["ok"] is False
    assert result["error"] == "Failed DB inspect"
    assert result["latency_ms"] == 0.0


def test_correlation_id_filter_header_and_g_exceptions():
    """A correlation ID should be generated when request access fails."""
    correlation_filter = CorrelationIdFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="msg",
        args=(),
        exc_info=None,
    )

    with patch(
        "app.g",
        new=PropertyMock(side_effect=RuntimeError),
    ):
        with patch(
            "app.request",
            new=PropertyMock(side_effect=RuntimeError),
        ):
            result = correlation_filter.filter(record)

    assert result is True
    assert record.correlation_id.startswith("cid-")


def test_register_core_routes_general_exception():
    """Route-registration errors should be logged."""
    app = Flask(__name__)

    with patch.object(
        app,
        "route",
        side_effect=RuntimeError("Route registration blocked"),
    ):
        with patch.object(
            app_module._logger,
            "debug",
        ) as mock_debug:
            _register_core_routes(app)

    mock_debug.assert_called_once_with(
        "_register_core_routes failed",
        exc_info=True,
    )


def test_rebuild_rules_by_endpoint_exception():
    """URL-map rebuilding errors should be logged."""
    app = Flask(__name__)
    app.url_map = MagicMock()
    app.url_map.iter_rules.side_effect = RuntimeError(
        "URL Map failure",
    )

    with patch.object(app.logger, "debug") as mock_debug:
        _rebuild_rules_by_endpoint(app)

    mock_debug.assert_called_once_with(
        "_rebuild_rules_by_endpoint failed",
        exc_info=True,
    )


def test_cleanup_premature_oauth_registrations_success():
    """Premature OAuth endpoints should be removed successfully."""
    app = _oauth_test_app()

    def fake_view():
        return "ok"

    fake_view.__module__ = "app.blueprints.oauth_routes.google"
    app.view_functions["oauth.google"] = fake_view

    class MockRule:
        endpoint = "oauth.google"

    rule = MockRule()

    app.url_map.iter_rules.return_value = [rule]
    app.url_map._rules = [rule]
    app.url_map._rules_by_endpoint = {
        "oauth.google": [rule],
    }

    with patch.object(app_module._logger, "info") as mock_info:
        _cleanup_premature_oauth_registrations(app)

    assert "oauth.google" not in app.view_functions

    mock_info.assert_called_with(
        "Removed premature oauth endpoints: %s",
        "oauth.google",
    )


def test_cleanup_premature_oauth_registrations_inner_exception():
    """Rule-removal exceptions should be caught and logged."""
    app = _oauth_test_app()

    def fake_view():
        return "ok"

    fake_view.__module__ = "app.blueprints.oauth_routes.google"
    app.view_functions["oauth.google"] = fake_view

    class MockRule:
        endpoint = "oauth.google"

    class FaultyRulesList(list):
        def remove(self, item):
            raise RuntimeError("Cannot remove rule")

    rule = MockRule()

    app.url_map.iter_rules.return_value = [rule]
    app.url_map._rules = FaultyRulesList([rule])
    app.url_map._rules_by_endpoint = {
        "oauth.google": FaultyRulesList([rule]),
    }

    with patch.object(app_module._logger, "debug") as mock_debug:
        _cleanup_premature_oauth_registrations(app)

    mock_debug.assert_any_call(
        "Failed to remove rule %r for endpoint %s",
        ANY,
        "oauth.google",
        exc_info=True,
    )


def test_cleanup_premature_oauth_registrations_outer_exception():
    """Top-level OAuth cleanup errors should be logged."""

    class BrokenApp:
        pass

    broken_app = BrokenApp()

    with patch.object(
        app_module._logger,
        "debug",
    ) as mock_debug:
        _cleanup_premature_oauth_registrations(broken_app)

    mock_debug.assert_called_once_with(
        "_cleanup_premature_oauth_registrations failed",
        exc_info=True,
    )


def test_add_route_prune_whitelist_and_pruning_exceptions():
    """Routes should be pruned while whitelisted endpoints are preserved."""
    original_whitelist = ROUTE_PRUNE_WHITELIST.copy()

    try:
        add_route_prune_whitelist("tmp_whitelisted_route")

        assert "tmp_whitelisted_route" in ROUTE_PRUNE_WHITELIST

        app = Flask(__name__)
        app.url_map = MagicMock()

        class MockRule:
            def __init__(self, endpoint, rule):
                self.endpoint = endpoint
                self.rule = rule

        rule_whitelisted = MockRule(
            "tmp_whitelisted_route",
            "/tmp/white",
        )
        rule_tmp = MockRule("tmp_test_route", "/test")
        rule_legacy = MockRule("legacy_route", "/legacy")
        rule_temp = MockRule("endpoint__temp", "/temp")
        rule_path_tmp = MockRule("normal_name", "/_tmp/path")

        rules = [
            rule_whitelisted,
            rule_tmp,
            rule_legacy,
            rule_temp,
            rule_path_tmp,
        ]

        class FaultyRulesList(list):
            def remove(self, item):
                raise RuntimeError(
                    "Rules list remove exception",
                )

        app.url_map._rules = FaultyRulesList(rules)
        app.url_map._rules_by_endpoint = {
            rule.endpoint: [rule] for rule in rules
        }
        app.url_map.iter_rules.return_value = rules

        for rule in rules:
            app.view_functions[rule.endpoint] = lambda: "ok"

        with patch.object(app_module._logger, "debug"):
            _prune_ignorable_route_rules(app)

        assert "tmp_whitelisted_route" in app.view_functions
        assert "tmp_test_route" not in app.view_functions

        class BrokenApp:
            @property
            def url_map(self):
                raise RuntimeError("URL map broken")

        broken_app = BrokenApp()

        with patch.object(
            app_module._logger,
            "debug",
        ) as mock_debug:
            _prune_ignorable_route_rules(broken_app)

            mock_debug.assert_any_call(
                "_prune_ignorable_route_rules failed",
                exc_info=True,
            )

    finally:
        ROUTE_PRUNE_WHITELIST.clear()

        if hasattr(
            ROUTE_PRUNE_WHITELIST,
            "update",
        ):
            ROUTE_PRUNE_WHITELIST.update(
                original_whitelist,
            )
        else:
            ROUTE_PRUNE_WHITELIST.extend(
                original_whitelist,
            )


def test_reconcile_oauth_callback_aliases_and_exceptions():
    """OAuth aliases should be removed while canonical callbacks remain."""
    app = Flask(__name__)
    app.url_map = MagicMock()

    alias_endpoint = "oauth.callback_google_alias"
    canonical_endpoint = "oauth.callback_google"

    app.view_functions[alias_endpoint] = lambda: "alias"
    app.view_functions[canonical_endpoint] = lambda: "canonical"

    class MockRule:
        def __init__(self, endpoint):
            self.endpoint = endpoint

    alias_rule = MockRule(alias_endpoint)
    canonical_rule = MockRule(canonical_endpoint)

    class FaultyList(list):
        def remove(self, item):
            raise RuntimeError("Removal failure")

    app.url_map._rules = FaultyList(
        [alias_rule, canonical_rule],
    )
    app.url_map._rules_by_endpoint = {
        alias_endpoint: FaultyList([alias_rule]),
        canonical_endpoint: [canonical_rule],
    }
    app.url_map.iter_rules.return_value = [
        alias_rule,
        canonical_rule,
    ]

    _reconcile_oauth_callback_aliases(app)

    assert alias_endpoint not in app.view_functions
    assert canonical_endpoint in app.view_functions

    class BrokenApp:
        pass

    broken_app = BrokenApp()

    with patch.object(
        app_module._logger,
        "debug",
    ) as mock_debug:
        _reconcile_oauth_callback_aliases(broken_app)

    mock_debug.assert_called_once_with(
        "_reconcile_oauth_callback_aliases failed",
        exc_info=True,
    )
