# =============================================================================
# FILE: app/tests/test_cli_top_level.py
# DESCRIPTION: Test suite for top-level Flask CLI commands and groups.
# =============================================================================

import json
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_redis():
    """Provide a mocked Redis client."""
    return MagicMock(name="mock_redis")


@pytest.fixture
def runner(app, mock_redis):
    """
    Provide a Flask CLI test runner with Redis and boot telemetry mocked.

    The application fixture is supplied by conftest.py.
    """
    with (
        patch(
            "app.cli_top_level.get_redis_client",
            return_value=mock_redis,
        ),
        patch("app.cli_top_level.emit_boot_trace") as mock_trace,
    ):
        app.mock_boot_trace = mock_trace
        yield app.test_cli_runner()


# =============================================================================
# HELPERS
# =============================================================================


def assert_cli_success(result):
    """
    Assert that a CLI command completed successfully.

    Including the CLI output and exception makes Click failures much easier to
    diagnose than a bare exit-code assertion.
    """
    assert result.exit_code == 0, (
        f"CLI command failed with exit code {result.exit_code}\n"
        f"Output:\n{result.output}\n"
        f"Exception:\n{result.exception!r}"
    )


def assert_cli_failure(result):
    """Assert that a CLI command failed and provide useful diagnostics."""
    assert result.exit_code != 0, (
        "CLI command unexpectedly succeeded.\n"
        f"Output:\n{result.output}"
    )


# =============================================================================
# BASELINE AND CLI ARGUMENT PARSING
# =============================================================================


def test_cli_help(runner):
    """Verify top-level CLI help executes successfully."""
    result = runner.invoke(args=["--help"])

    assert_cli_success(result)
    assert "Usage:" in result.output


def test_cli_invalid_parameter_values(runner):
    """Verify an invalid top-level option is rejected."""
    result = runner.invoke(args=["--invalid-flag"])

    assert_cli_failure(result)
    assert "Error: No such option" in result.output


def test_cli_unknown_command(runner):
    """Verify an unregistered command is rejected."""
    result = runner.invoke(args=["non-existent-command"])

    assert_cli_failure(result)
    assert "Error: No such command" in result.output


def test_cli_hello_command_unregistered(runner):
    """Verify the decommissioned hello command is strictly rejected."""
    result = runner.invoke(args=["hello"])

    assert_cli_failure(result)
    assert "Error: No such command" in result.output


# =============================================================================
# ENV-DOCTOR COMMAND
# =============================================================================


class TestEnvDoctorCommand:
    def test_env_doctor_success(self, runner):
        """Verify env-doctor executes successfully."""
        with patch(
            "app.cli_top_level.emit_boot_trace"
        ) as mock_emit:
            result = runner.invoke(args=["env-doctor"])

        assert_cli_success(result)
        assert "Environment Doctor" in result.output
        mock_emit.assert_called_once()

    def test_env_doctor_telemetry_failure(self, runner):
        """Verify env-doctor handles telemetry failures cleanly."""
        with patch(
            "app.cli_top_level.emit_boot_trace",
            side_effect=Exception("Telemetry exception"),
        ) as mock_emit:
            result = runner.invoke(args=["env-doctor"])

        assert_cli_success(result)
        assert mock_emit.call_count == 2
        assert (
            mock_emit.call_args_list[1].kwargs.get("status")
            == "error"
        )


# =============================================================================
# CORTEX COMMAND GROUP
# =============================================================================


class TestCortexGroup:
    def test_cortex_command_is_registered(self, runner):
        """Verify the cortex group and its expected subcommands are registered."""
        cortex_command = runner.app.cli.commands.get("cortex")

        assert cortex_command is not None, (
            "The 'cortex' command group is not registered. "
            f"Registered commands: "
            f"{sorted(runner.app.cli.commands.keys())}"
        )

        subcommands = getattr(cortex_command, "commands", {})
        assert "status" in subcommands
        assert "enable" in subcommands
        assert "disable" in subcommands

    def test_cortex_status_enabled(self, runner):
        """Verify cortex status when Cortex is enabled."""
        with patch("app.cli_top_level.cortex") as mock_cortex:
            mock_cortex.is_enabled = True

            result = runner.invoke(args=["cortex", "status"])

        assert_cli_success(result)
        assert "ENABLED" in result.output.upper()

    def test_cortex_status_disabled(self, runner):
        """Verify cortex status when Cortex is disabled."""
        with patch("app.cli_top_level.cortex") as mock_cortex:
            mock_cortex.is_enabled = False

            result = runner.invoke(args=["cortex", "status"])

        assert_cli_success(result)
        assert "DISABLED" in result.output.upper()

    def test_cortex_enable(self, runner):
        """Verify cortex enable executes successfully."""
        with patch("app.cli_top_level.cortex") as mock_cortex:
            result = runner.invoke(args=["cortex", "enable"])

        assert_cli_success(result)
        mock_cortex.enable.assert_called_once_with()

    def test_cortex_disable(self, runner):
        """Verify cortex disable executes successfully."""
        with patch("app.cli_top_level.cortex") as mock_cortex:
            result = runner.invoke(args=["cortex", "disable"])

        assert_cli_success(result)
        mock_cortex.disable.assert_called_once_with()


# =============================================================================
# INSPECTION COMMANDS
# =============================================================================


def test_cli_routes_command(runner):
    """Verify Flask route inspection executes successfully."""
    result = runner.invoke(args=["routes"])

    assert_cli_success(result)
    assert "Endpoint" in result.output or "Rule" in result.output


def test_audit_templates_command(runner):
    """Verify audit-templates returns valid JSON."""
    result = runner.invoke(args=["audit-templates"])

    assert_cli_success(result)

    parsed = json.loads(result.output)
    assert isinstance(parsed, list)


# =============================================================================
# DATABASE MIGRATIONS COMMAND GROUP
# =============================================================================


class TestDatabaseGroup:
    def test_db_upgrade_success(self, runner):
        """Verify successful database migration upgrade."""
        with (
            patch(
                "app.cli_top_level.get_current_revision",
                side_effect=["rev_100", "rev_200"],
            ),
            patch("app.cli_top_level.upgrade") as mock_upgrade,
            patch(
                "app.cli_top_level.emit_boot_trace"
            ) as mock_emit,
        ):
            result = runner.invoke(args=["db", "upgrade"])

        assert_cli_success(result)
        mock_upgrade.assert_called_once()

        assert mock_emit.call_count == 2

        first_value = mock_emit.call_args_list[0].kwargs.get("value", "")
        second_value = mock_emit.call_args_list[1].kwargs.get("value", "")

        assert "from_rev:rev_100" in first_value
        assert "success:to_rev:rev_200" in second_value

    def test_db_upgrade_failure(self, runner):
        """Verify migration failures are reported and traced."""
        with (
            patch(
                "app.cli_top_level.get_current_revision",
                return_value="rev_100",
            ),
            patch(
                "app.cli_top_level.upgrade",
                side_effect=RuntimeError("Migration script failed"),
            ),
            patch(
                "app.cli_top_level.emit_boot_trace"
            ) as mock_emit,
        ):
            result = runner.invoke(args=["db", "upgrade"])

        assert_cli_failure(result)
        assert mock_emit.call_count == 2
        assert (
            mock_emit.call_args_list[1].kwargs.get("status")
            == "error"
        )


# =============================================================================
# DOCTOR-PA COMMAND
# =============================================================================


class TestDoctorPACommand:
    def test_doctor_pa_success(self, runner):
        """Verify successful PythonAnywhere-safe doctor execution."""
        with patch(
            "app.cli_top_level.emit_boot_trace"
        ) as mock_emit:
            result = runner.invoke(args=["doctor-pa"])

        assert_cli_success(result)
        assert "PA Doctor" in result.output
        mock_emit.assert_called_once()

    def test_doctor_pa_telemetry_failure(self, runner):
        """Verify doctor-pa handles telemetry failures."""
        with patch(
            "app.cli_top_level.emit_boot_trace",
            side_effect=Exception("Telemetry failure"),
        ) as mock_emit:
            result = runner.invoke(args=["doctor-pa"])

        assert_cli_success(result)
        assert mock_emit.call_count == 2
        assert (
            mock_emit.call_args_list[1].kwargs.get("status")
            == "error"
        )