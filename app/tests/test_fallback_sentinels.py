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
    import app.extensions

    # 💥 SABOTAGE: The factory is too robust! We have to actively force
    # a fatal crash in a core initialization step so it triggers the fallback guard.
    def fatal_crash(*args, **kwargs):
        raise RuntimeError("Simulated fatal boot crash!")

    monkeypatch.setattr(app.extensions, "init_extensions", fatal_crash)

    try:
        # Reload to trigger fallback guard
        importlib.reload(app_module)

        # --- Core sentinel checks ---
        assert getattr(app_module, "app", None) is not None, "Fallback app was not exported"
        assert isinstance(app_module.app, Flask)
        assert app_module.app.config.get("SAFE_MODE") is True
        assert app_module.app.config.get("FALLBACK_MODE") is True
        assert app_module.app.config.get("PROPAGATE_EXCEPTIONS") is False

        # --- Log expectations ---
        # Updated to match the actual CRITICAL log output from the app boot sequence
        assert any("FATAL BOOT ERROR" in rec.message for rec in caplog.records)
        assert any("Sentinel override active" in rec.message for rec in caplog.records)
        assert any("Emergency Safe-Mode Fallback App" in rec.message for rec in caplog.records)

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

    finally:
        # 🧼 CLEANUP: Because app/__init__.py performs module-level imports and executions
        # during reload, the sabotaged function leaks into sys.modules['app']. We must
        # undo the monkeypatch and force a clean reload so subsequent tests aren't poisoned.
        monkeypatch.undo()
        importlib.reload(app_module)