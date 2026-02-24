# =============================================================================
# FILE: tests/test_emit_blueprint_inspector_cli.py
# DESCRIPTION: Tests for the emit_blueprint_inspector CLI command.
# =============================================================================

import pytest
from click.testing import CliRunner

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
        "app.cockpit.tiles.blueprint_inspector.emit_to_redis",
        fake_emit_to_redis,
    )

    def fake_emit_ttl_trace(key, msg, ttl):
        assert key.endswith("summary")
        assert isinstance(msg, dict)
        assert ttl == 3600
        calls["ttl"] += 1

    monkeypatch.setattr(
        "app.utils.redis_trace.emit_ttl_trace",
        fake_emit_ttl_trace,
    )

    def fake_log_identity_event(event, user_id, meta):
        assert event == "BLUEPRINT_INSPECTOR_EMIT"
        assert user_id == 0
        assert meta["status"] == "emitted"
        calls["telemetry"] += 1

    monkeypatch.setattr(
        "app.utils.telemetry.log_identity_event",
        fake_log_identity_event,
    )

    return calls


def test_cli_emit_blueprint_inspector(stub_dependencies):
    """
    Verify the CLI command:
      • exits with code 0
      • prints confirmation message
      • calls each stubbed dependency exactly once
    """
    runner = CliRunner()
    result = runner.invoke(emit_blueprint_inspector)

    assert result.exit_code == 0
    assert "✅" in result.output
    assert "Redis" in result.output

    calls = stub_dependencies
    assert calls["emit"] == 1
    assert calls["ttl"] == 1
    assert calls["telemetry"] == 1
