# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_fallback_sentinels.py

import importlib
import logging
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
    caplog.set_level(logging.ERROR)

    import app as app_module
    import app.extensions

    # Ensure log records reach the root logger caplog fixture across all app namespaces
    for logger_name in ("app", "flask.app", "PlaidBridgeOpenBankingApi"):
        log_obj = logging.getLogger(logger_name)
        log_obj.propagate = True
        log_obj.addHandler(caplog.handler)

    # Force a fatal crash during core extension initialization
    def fatal_crash(*args, **kwargs):
        raise RuntimeError("Simulated fatal boot crash!")

    monkeypatch.setattr(app.extensions, "init_extensions", fatal_crash)

    try:
        # Reload module to trigger fallback initialization
        importlib.reload(app_module)

        # Core sentinel checks
        assert getattr(app_module, "app", None) is not None, "Fallback app was not exported"
        assert isinstance(app_module.app, Flask)
        assert app_module.app.config.get("SAFE_MODE") is True
        assert app_module.app.config.get("FALLBACK_MODE") is True
        assert app_module.app.config.get("PROPAGATE_EXCEPTIONS") is False

        # Log expectations
        assert any("FATAL BOOT ERROR" in rec.message for rec in caplog.records), (
            f"Expected 'FATAL BOOT ERROR' in logs. Captured records: {[r.message for r in caplog.records]}"
        )

        # Endpoint checks
        client = app_module.app.test_client()
        for endpoint in ["/healthz", "/readyz", "/version", "/diagnostics"]:
            res = client.get(endpoint)
            assert res.status_code in (200, 503)
            data = res.get_json()
            assert isinstance(data, dict)

    finally:
        monkeypatch.undo()
        importlib.reload(app_module)