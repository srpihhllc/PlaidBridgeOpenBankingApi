"""
/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_admin_alias_registration.py
"""

import pytest
from flask import url_for
from werkzeug.routing.converters import IntegerConverter, FloatConverter


def _build_dummy_args_for_rule(rule):
    """Generates valid type-matched dummy arguments for dynamic Werkzeug route parameters."""
    dummy_args = {}
    for name, converter in rule._converters.items():
        if isinstance(converter, (IntegerConverter, FloatConverter)):
            dummy_args[name] = 1
        else:
            dummy_args[name] = "test"
    return dummy_args


def test_admin_ui_alias_endpoint_registered(app):
    """Verify that 'admin_ui.admin_index' exists in view_functions and url_map."""
    assert "admin_ui.admin_index" in app.view_functions
    assert (
        app.view_functions["admin_ui.admin_index"]
        == app.view_functions["admin.admin_index"]
    )

    with app.test_request_context():
        resolved_url = url_for("admin_ui.admin_index")
        assert resolved_url == "/admin/"


def test_admin_ui_aliases_all_canonical_routes(app):
    """Verify all admin.* endpoints have corresponding admin_ui.* aliases."""
    with app.test_request_context():
        # Get all registered canonical rules under admin.*
        admin_rules = [
            r
            for r in app.url_map.iter_rules()
            if r.endpoint.startswith("admin.")
        ]

        for rule in admin_rules:
            canonical_ep = rule.endpoint
            alias_ep = f"admin_ui.{canonical_ep.split('.', 1)[1]}"

            # 1. Check view function mapping
            assert (
                alias_ep in app.view_functions
            ), f"Missing view_function for {alias_ep}"

            # 2. Build parameter mapping matched to expected converter types
            dummy_args = _build_dummy_args_for_rule(rule)

            try:
                canonical_url = url_for(canonical_ep, **dummy_args)
                alias_url = url_for(alias_ep, **dummy_args)
                assert (
                    alias_url == canonical_url
                ), f"URL mismatch for {alias_ep}: {alias_url} != {canonical_url}"
            except Exception as e:
                pytest.fail(
                    f"url_for('{alias_ep}') raised {type(e).__name__}: {e}"
                )
