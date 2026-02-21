# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_template_tracer.py

import pytest
from flask import Flask

from app.cockpit.template_tracer import PARAMETERIZED_ENDPOINTS, trace_templates


@pytest.fixture
def app():
    app = Flask(__name__)
    from app.blueprints import register_blueprints

    register_blueprints(app)
    return app


def test_trace_templates_runs(app):
    results = trace_templates(app)
    assert isinstance(results, list)
    assert all("endpoint" in r for r in results)


def test_parameterized_endpoints_map():
    for ep, dummy in PARAMETERIZED_ENDPOINTS.items():
        assert isinstance(ep, str)
        assert isinstance(dummy, str)


def test_drilldown_endpoint(app):
    results = trace_templates(app)
    drilldown = next((r for r in results if r["endpoint"] == "drilldown.drilldown_view"), None)
    assert drilldown is not None
    assert drilldown["status"] == "ok"
