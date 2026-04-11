# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_template_tracer.py

# app/tests/test_template_tracer.py
"""
Tests for app.cockpit.template_tracer.

Key architectural facts (see sources below):
  - trace_templates() iterates app.url_map — it can only report endpoints
    that are actually registered on the app under test.
  - drilldown_bp lives in app/cockpit/routes/drilldown.py; it is NOT under
    app/blueprints/ so register_blueprints() never discovers it.
  - The bare Flask(__name__) + register_blueprints() fixture therefore never
    registers drilldown_bp, making "drilldown.drilldown_view" invisible to
    trace_templates() and causing test_drilldown_endpoint to fail with
    "assert None is not None".

Fix: use create_app() (the real factory) as the fixture so every blueprint —
including cockpit ones — is registered exactly as in production.  The
test_request_context approach inside trace_templates() does not need a real
DB; heavy I/O failures are caught and recorded as "error" status, which is
fine for smoke-testing the wiring.
"""

from __future__ import annotations

import pytest

from app.cockpit.template_tracer import PARAMETERIZED_ENDPOINTS, trace_templates


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tracer_app():
    """
    Return a fully-initialised Flask app produced by create_app().

    Using the real factory ensures ALL blueprints (including cockpit ones such
    as drilldown_bp that live outside app/blueprints/) are registered — which
    is the prerequisite for trace_templates() to find them.

    scope="module" keeps app creation to once per test module; the tracer
    never writes to the DB so session isolation is not needed here.
    """
    from app import create_app  # adjust if your factory lives elsewhere

    app = create_app()
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _results_by_endpoint(app) -> dict[str, dict]:
    """Run trace_templates and index results by endpoint name."""
    results = trace_templates(app)
    return {r["endpoint"]: r for r in results}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_trace_templates_returns_list(tracer_app):
    """trace_templates must always return a list of dicts with an 'endpoint' key."""
    results = trace_templates(tracer_app)
    assert isinstance(results, list), "trace_templates() must return a list"
    assert len(results) > 0, "Expected at least one route to be traced"
    for r in results:
        assert "endpoint" in r, f"Result missing 'endpoint' key: {r}"
        assert "status" in r, f"Result missing 'status' key: {r}"
        assert r["status"] in (
            "ok",
            "error",
            "missing_template",
        ), f"Unexpected status value: {r['status']!r} for endpoint {r['endpoint']!r}"


def test_parameterized_endpoints_map_types():
    """Every entry in PARAMETERIZED_ENDPOINTS must be str → str."""
    assert isinstance(PARAMETERIZED_ENDPOINTS, dict), "PARAMETERIZED_ENDPOINTS must be a dict"
    for ep, dummy in PARAMETERIZED_ENDPOINTS.items():
        assert isinstance(ep, str), f"Key must be str, got {type(ep)} for {ep!r}"
        assert isinstance(dummy, str), f"Value must be str, got {type(dummy)} for key {ep!r}"


def test_drilldown_blueprint_is_registered(tracer_app):
    """
    drilldown_bp must be registered on the app.

    If this fails, the blueprint was not included in create_app() (or whatever
    factory is used).  Fix: ensure create_app() calls
    app.register_blueprint(drilldown_bp) or that drilldown_bp is registered
    via init_app / register_blueprints.
    """
    registered = set(tracer_app.blueprints.keys())
    assert "drilldown" in registered, (
        f"Blueprint 'drilldown' is not registered on the app. "
        f"Registered blueprints: {sorted(registered)}. "
        f"Ensure create_app() registers app/cockpit/routes/drilldown.py."
    )


def test_drilldown_endpoint_present_in_url_map(tracer_app):
    """
    'drilldown.drilldown_view' must appear in the URL map before trace_templates
    can ever return a result for it.
    """
    endpoints = {r.endpoint for r in tracer_app.url_map.iter_rules()}
    assert "drilldown.drilldown_view" in endpoints, (
        f"Endpoint 'drilldown.drilldown_view' not found in url_map. "
        f"Registered endpoints (sample): {sorted(endpoints)[:20]}"
    )


def test_drilldown_endpoint_traced(tracer_app):
    """
    trace_templates() must include a result for 'drilldown.drilldown_view'
    and that result must have status 'ok'.

    The drilldown view renders a template from disk; it does NOT touch the DB,
    so it should succeed in a test_request_context even without a real DB.
    """
    indexed = _results_by_endpoint(tracer_app)

    assert "drilldown.drilldown_view" in indexed, (
        "'drilldown.drilldown_view' was not traced by trace_templates(). "
        "Ensure the blueprint is registered AND the endpoint supports GET."
    )

    result = indexed["drilldown.drilldown_view"]
    assert result["status"] == "ok", (
        f"drilldown.drilldown_view traced with status={result['status']!r}.\n"
        f"Error detail:\n{result.get('error', '(none)')}"
    )


def test_no_endpoint_raises_unhandled_exception(tracer_app):
    """
    trace_templates() must never propagate an unhandled exception — every
    failure must be caught and recorded as an 'error' or 'missing_template'
    result.  This guards against future regressions in the tracer itself.
    """
    # If trace_templates raises, the test fails with the raw exception,
    # which is the desired behaviour.
    results = trace_templates(tracer_app)
    assert results is not None


def test_parameterized_endpoints_are_reachable(tracer_app):
    """
    Every endpoint listed in PARAMETERIZED_ENDPOINTS that is actually
    registered on the app must appear in the trace results (status ok or
    error/missing_template — not absent).

    This catches the case where PARAMETERIZED_ENDPOINTS references an
    endpoint name that was renamed or removed.
    """
    registered_endpoints = {r.endpoint for r in tracer_app.url_map.iter_rules()}
    indexed = _results_by_endpoint(tracer_app)

    missing_from_trace = []
    not_registered = []
    for ep in PARAMETERIZED_ENDPOINTS:
        if ep not in registered_endpoints:
            not_registered.append(ep)
            continue
        if ep not in indexed:
            missing_from_trace.append(ep)

    assert not missing_from_trace, (
        f"These PARAMETERIZED_ENDPOINTS are registered but were not traced: "
        f"{missing_from_trace}"
    )
    # Not-registered entries are reported as warnings, not failures, because
    # PARAMETERIZED_ENDPOINTS may intentionally list future endpoints.
    if not_registered:
        import warnings
        warnings.warn(
            f"PARAMETERIZED_ENDPOINTS references endpoints not yet registered: "
            f"{not_registered}",
            stacklevel=1,
        )