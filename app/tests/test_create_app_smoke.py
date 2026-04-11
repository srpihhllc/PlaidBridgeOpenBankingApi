# name=app/tests/test_create_app_smoke.py
from app import create_app
from app.config import TestingConfig

def test_create_app_and_basic_endpoints():
    app = create_app(config_class=TestingConfig)
    # Basic sanity checks: testing mode and a few endpoints exist
    assert app.config.get("TESTING") is True
    # Ensure some lightweight endpoints are present
    assert "/health" in {r.rule for r in app.url_map.iter_rules()}
    # Create client and call a trivial endpoint
    client = app.test_client()
    rv = client.get("/health")
    assert rv.status_code in (200, 503)  # health may depend on DB; accept either