# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_fallback_sentinels.py

import pytest
from flask import Flask

@pytest.mark.smoketest
def test_fallback_sentinels(monkeypatch, caplog):
    """
    Validate that the fallback app created when FLASK_ENV=production is:
      - a Flask instance
      - has SAFE_MODE and FALLBACK_MODE flags
      - sets PROPAGATE_EXCEPTIONS = False
      - exposes fallback endpoints (/healthz, /readyz, /version, /diagnostics)
      - returns structured fallback payloads
    """
    monkeypatch.setenv("FLASK_ENV", "production")
    caplog.set_level("CRITICAL")

    import importlib
    import app as app_module

    # Reload to trigger fallback guard
    importlib.reload(app_module)

    # --- Core sentinel checks ---
    assert isinstance(app_module.app, Flask)
    assert app_module.app.config["SAFE_MODE"] is True
    assert app_module.app.config["FALLBACK_MODE"] is True
    assert app_module.app.config["PROPAGATE_EXCEPTIONS"] is False

    # --- Log expectations ---
    assert any("UNSAFE FALLBACK APP CREATED" in rec.message for rec in caplog.records)
    assert any("fallback_app_created" in rec.message for rec in caplog.records)
    assert any("Operator hint" in rec.message for rec in caplog.records)

    client = app_module.app.test_client()

    # --- /diagnostics ---
    resp = client.get("/diagnostics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["safe_mode"] is True
    assert data["fallback_mode"] is True
    assert data["create_app_invoked"] is False

    # --- /healthz ---
    resp = client.get("/healthz")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["healthy"] is False
    assert "fallback" in data["checks"]

    # --- /readyz ---
    resp = client.get("/readyz")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["ready"] is False
    assert "fallback" in data["checks"]

    # --- /version ---
    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fallback_mode"] is True
