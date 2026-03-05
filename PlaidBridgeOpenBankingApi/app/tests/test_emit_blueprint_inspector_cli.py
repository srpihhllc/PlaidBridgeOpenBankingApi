# =============================================================================
# FILE: tests/test_emit_blueprint_inspector_cli.py
# DESCRIPTION: Tests for the emit_blueprint_inspector CLI command.
# =============================================================================

import pytest

from app.cli_commands.emit_blueprint_inspector import emit_blueprint_inspector


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    """
    Stub out Redis emit, TTL trace, and telemetry logging.
    Tracks call counts for verification.
    """
    calls = {"emit": 0, "ttl": 0, "telemetry": 0}

    def fake_emit_to_redis():
        calls["emit"] += 1
        return [{"name": "bp1"}, {"name": "bp2"}]

    monkeypatch.setattr(
        "app.cli_commands.emit_blueprint_inspector.emit_to_redis",
        fake_emit_to_redis,
    )

    def fake_emit_schema_trace(domain, event, detail, value, status, ttl=60, client=None, meta=None):
        assert detail == "summary"
        assert ttl == 3600
        calls["ttl"] += 1

    monkeypatch.setattr(
        "app.cli_commands.emit_blueprint_inspector.emit_schema_trace",
        fake_emit_schema_trace,
    )

    def fake_log_identity_event(user_id, event_type, ip=None, user_agent=None, details=None):
        assert event_type == "BLUEPRINT_INSPECTOR_EMIT"
        assert user_id == 0
        assert details["status"] == "emitted"
        calls["telemetry"] += 1

    monkeypatch.setattr(
        "app.cli_commands.emit_blueprint_inspector.log_identity_event",
        fake_log_identity_event,
    )

    return calls


def test_cli_emit_blueprint_inspector(stub_dependencies, app):
    """
    Verify the CLI command:
      • exits with code 0
      • prints confirmation message
      • calls each stubbed dependency exactly once
    """
    result = app.test_cli_runner().invoke(emit_blueprint_inspector)

    assert result.exit_code == 0
    assert "✅" in result.output
    assert "Redis" in result.output

    calls = stub_dependencies
    assert calls["emit"] == 1
    assert calls["ttl"] == 1
    assert calls["telemetry"] == 1
