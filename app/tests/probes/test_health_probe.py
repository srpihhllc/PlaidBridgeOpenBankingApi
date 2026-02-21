# =============================================================================
# FILE: app/tests/probes/test_health_probe.py
# DESCRIPTION: Unit test for /api/v1/health probe endpoint.
# =============================================================================


def test_probes_health_endpoint(client):
    """The health endpoint should return 200 and a status of 'ok'."""
    # FIX: Point to the actual URL defined in api_v1_routes.py
    # Note: If your api_v1_bp also has a url_prefix='/api/v1',
    # the URL might actually be '/api/v1/api/v1/health'.
    # Based on your snippet, let's try the direct path first:
    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.get_json()

    # FIX: Your success_response nests data inside 'data'
    assert body["status"] == "success"
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] == "ok"
