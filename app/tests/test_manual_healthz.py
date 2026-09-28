# app/tests/test_manual_healthz.py

def test_healthz_manually(client):
    response = client.get("/healthz")

    assert response.status_code in (200, 503)

    body = response.get_json()
    assert isinstance(body, dict)
    assert "healthy" in body
    assert "timestamp" in body
    assert "uptime" in body
    assert "checks" in body