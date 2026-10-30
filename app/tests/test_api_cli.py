#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_api_cli.py

from flask import Flask

from app.api import api_bp
from app.cli import register_cli_commands


def create_test_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    register_cli_commands(app)
    return app


def test_health_check():
    app = create_test_app()
    client = app.test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "service": "PlaidBridgeOpenBankingApi",
    }


def test_verify_sandbox_command():
    app = create_test_app()
    runner = app.test_cli_runner()

    result = runner.invoke(args=["verify-sandbox"])

    assert result.exit_code == 0
    assert "Verifying Sandbox environment..." in result.output


def test_init_db_command():
    app = create_test_app()
    runner = app.test_cli_runner()

    result = runner.invoke(args=["init-db"])

    assert result.exit_code == 0
    assert "Initializing database..." in result.output