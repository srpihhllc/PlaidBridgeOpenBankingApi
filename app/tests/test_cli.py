#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_cli.py

from app.cli import register_cli_commands


def test_verify_sandbox_command(app):
    register_cli_commands(app)

    runner = app.test_cli_runner()
    result = runner.invoke(args=["verify-sandbox"])

    assert result.exit_code == 0
    assert result.output == "Verifying Sandbox environment...\n"


def test_init_db_command(app):
    register_cli_commands(app)

    runner = app.test_cli_runner()
    result = runner.invoke(args=["init-db"])

    assert result.exit_code == 0
    assert result.output == "Initializing database...\n"