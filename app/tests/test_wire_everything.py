# =============================================================================
# FILE: app/tests/test_wire_everything.py
# DESCRIPTION: Smoketests for wiring of templates, UI blueprints, and Redis payloads.
# =============================================================================
import json

import pytest

from app.utils.redis_utils import get_redis_client


@pytest.mark.smoketest
def test_sub_index_renders(client):
    """Subscriber UI index should render and list templates."""
    resp = client.get("/sub/")
    assert resp.status_code == 200
    assert b"subscriber_dashboard.html" in resp.data or b"templates" in resp.data


@pytest.mark.smoketest
def test_admin_index_renders(client, app):
    """Admin UI index should render and list admin templates."""
    resp = client.get("/admin")
    assert resp.status_code in (200, 302)


@pytest.mark.smoketest
def test_sub_template_render(client):
    """Subscriber UI should render a whitelisted template via /sub/t/<tpl>."""
    resp = client.get("/sub/t/subscriber_dashboard.html")
    assert resp.status_code == 200
    assert b"Welcome" in resp.data or b"Dashboard" in resp.data


@pytest.mark.smoketest
def test_admin_template_render(client):
    """Admin UI should render a whitelisted admin template via /admin/t/<tpl>."""
    resp = client.get("/admin/t/admin_console.html")
    assert resp.status_code in (200, 302)


@pytest.mark.smoketest
def test_home_renders(client):
    """Main home page should render without error."""
    resp = client.get("/")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert b"PlaidBridge" in resp.data or b"Welcome" in resp.data


@pytest.mark.smoketest
def test_dashboard_renders(client, auth_headers):
    """Subscriber dashboard should render with valid auth headers."""
    resp = client.get("/dashboard", headers=auth_headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


@pytest.mark.smoketest
def test_welcome_back_renders(client, auth_headers):
    """Welcome back page should render with valid auth headers."""
    resp = client.get("/welcome_back", headers=auth_headers)
    assert resp.status_code == 200
    assert b"Welcome Back" in resp.data or b"ttl" in resp.data


# --- NEW TESTS FOR REDIS WIRING PAYLOADS ---


@pytest.mark.smoketest
def test_wiring_payload_in_redis(app):
    """Ensure tracer/audit emit unified wiring payload into Redis."""
    r = get_redis_client()
    raw = r.get("audit:template_wiring")
    assert raw, "Expected audit:template_wiring key in Redis"
    payload = json.loads(raw.decode("utf-8"))

    # Basic shape checks
    assert isinstance(payload, list)
    assert all("status" in entry for entry in payload)

    # Ensure at least one entry is either MISSING_TEMPLATE or MISSING_ENDPOINT
    statuses = {entry["status"] for entry in payload}
    assert statuses.intersection(
        {"MISSING_TEMPLATE", "MISSING_ENDPOINT", "ERROR", "OK"}
    ), f"Unexpected statuses in payload: {statuses}"


@pytest.mark.smoketest
def test_template_wiring_tile_endpoint(client):
    """Ensure cockpit tile endpoint returns wiring payload from Redis."""
    resp = client.get("/cockpit/template_wiring")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert isinstance(data["payload"], list)
    assert data["count"] == len(data["payload"])
    # Check that statuses are present
    statuses = {entry["status"] for entry in data["payload"]}
    assert statuses.intersection(
        {"MISSING_TEMPLATE", "MISSING_ENDPOINT", "ERROR", "OK"}
    ), f"Unexpected statuses in tile payload: {statuses}"


@pytest.mark.smoketest
def test_payload_contains_fix_details(app):
    """Ensure wiring payload entries include explicit fix details."""
    r = get_redis_client()
    raw = r.get("audit:template_wiring")
    assert raw, "Expected audit:template_wiring key in Redis"
    payload = json.loads(raw.decode("utf-8"))

    for entry in payload:
        if entry["status"] == "MISSING_TEMPLATE":
            assert (
                "Created placeholder" in entry["error"]
            ), f"Missing placeholder fix detail in {entry}"
        if entry["status"] == "MISSING_ENDPOINT":
            assert "url_for" in entry["error"], f"Missing endpoint fix detail in {entry}"


# --- OPTIONAL: Inject dummy payload for isolated testing ---


@pytest.mark.smoketest
def test_inject_dummy_payload_and_tile(client, app):
    """Inject a dummy payload into Redis and verify tile endpoint returns it."""
    dummy_payload = [
        {
            "endpoint": "letters.preview_letter",
            "rule": "/letters/preview/<int:letter_id>",
            "template": "letters/preview_letter.html",
            "status": "MISSING_TEMPLATE",
            "error": "Created placeholder at app/templates/letters/preview_letter.html",
        },
        {
            "template": "dashboard.html",
            "status": "MISSING_ENDPOINT",
            "error": "url_for('subscriber.dashboard') not found",
        },
    ]
    r = get_redis_client()
    r.set("audit:template_wiring", json.dumps(dummy_payload))

    resp = client.get("/cockpit/template_wiring")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["payload"] == dummy_payload
    assert data["count"] == len(dummy_payload)
