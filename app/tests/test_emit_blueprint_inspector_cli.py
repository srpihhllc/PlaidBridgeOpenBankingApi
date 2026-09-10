# =============================================================================
# FILE: tests/test_emit_blueprint_inspector_cli.py
# DESCRIPTION: Tests for the emit_blueprint_inspector CLI command.
# =============================================================================

import pytest

from app import create_app
from app.cli_commands.emit_blueprint_inspector import emit_blueprint_inspector


@pytest.fixture
def app():
    """Boot the test app with testing configuration."""
    app = create_app("testing")
    return app


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    """
    Stub out Redis emit, TTL trace, and telemetry logging.
    Tracks call counts for verification.
    """
    calls = {"emit": 0, "ttl": 0, "telemetry": 0}

    # --- Redis emit stub ---
    def fake_emit_to_redis():
        calls["emit"] += 1
        return [{"name": "bp1"}, {"name": "bp2"}]

    monkeypatch.setattr(
        "app.cockpit.tiles.blueprint_inspector.emit_to_redis",
        fake_emit_to_redis,
    )

    # --- TTL trace stub ---
    def fake_emit_ttl_trace(key, msg, ttl=3600):
        assert key.endswith("summary")
        assert isinstance(msg, dict)
        assert ttl == 3600
        calls["ttl"] += 1

    monkeypatch.setattr(
        "app.utils.redis_trace.emit_ttl_trace",
        fake_emit_ttl_trace,
    )

    # --- UNIVERSAL TELEMETRY STUB (auto‑adapts to any signature) ---
    def fake_log_identity_event(*args, **kwargs):
        """
        Supports all known telemetry signatures:
        • log_identity_event(user_id, event_type, ip=None, user_agent=None, details=None)
        • log_identity_event(event, code, meta)
        • log_identity_event(event="...", code=0, meta={...})
        """

        # Normalize event_type
        if "event_type" in kwargs:
            event_type = kwargs["event_type"]
        elif "event" in kwargs:
            event_type = kwargs["event"]
        else:
            # CLI signature: (user_id, event_type, ...)
            event_type = args[1]

        assert event_type == "BLUEPRINT_INSPECTOR_EMIT"

        # Normalize details/meta
        if "details" in kwargs:
            details = kwargs["details"]
        elif "meta" in kwargs:
            details = kwargs["meta"]
        else:
            # CLI signature: args[2] = {"details": {...}}
            details = args[2]

        assert isinstance(details, dict)
        assert details.get("status") == "emitted"

        calls["telemetry"] += 1

    # ⭐ Correct monkeypatch target — CLI imports log_identity_event directly
    monkeypatch.setattr(
        "app.utils.telemetry.log_identity_event",
        fake_log_identity_event,
    )

    return calls


def test_cli_emit_blueprint_inspector(app, stub_dependencies):
    """
    Verify the CLI command:
      • exits with code 0
      • prints confirmation message
      • calls each stubbed dependency exactly once
    """
    runner = app.test_cli_runner()
    result = runner.invoke(emit_blueprint_inspector)

    assert (
        result.exit_code == 0
    ), f"Command failed: {result.output} | Exception: {result.exception}"
    assert "✅" in result.output
    assert "Redis" in result.output

    calls = stub_dependencies
    assert calls["emit"] == 1
    assert calls["ttl"] == 1
    assert calls["telemetry"] == 1
