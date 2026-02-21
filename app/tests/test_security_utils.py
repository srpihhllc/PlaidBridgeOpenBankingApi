# =============================================================================
# FILE: tests/test_security_utils.py
# DESCRIPTION: Unit tests for app/utils/security_utils.py
# =============================================================================

import json
import logging

import pytest
from flask import Flask
from flask_wtf import CSRFProtect

from app.utils import security_utils


@pytest.fixture
def app():
    """Provide a minimal Flask app with CSRF and request_id middleware."""
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=True,
        SECRET_KEY="test-secret-key",
    )

    # Inject request ID middleware
    security_utils.inject_request_id(app)

    # Initialize CSRF protection (mirrors app/__init__.py)
    CSRFProtect(app)

    return app


@pytest.fixture
def client(app):
    """Provide a test client for the Flask app."""
    return app.test_client()


def test_security_request_id_injected(client, app):
    """Every request should have a request_id injected into the response meta."""

    @app.route("/ping")
    def ping():
        return security_utils.success_response({"pong": True})

    resp = client.get("/ping")
    data = resp.get_json()
    assert resp.status_code == 200
    assert "request_id" in data["meta"]
    assert isinstance(data["meta"]["request_id"], str)
    assert data["meta"]["request_id"] != "N/A"


def test_security_get_request_id_defaults_outside_request():
    """Outside a request context, get_request_id should return 'N/A'."""
    assert security_utils.get_request_id() == "N/A"


def test_security_success_response_schema(app):
    """success_response should return a uniform envelope with meta and data."""
    with app.test_request_context("/"):
        resp, status = security_utils.success_response(
            data={"foo": "bar"}, message="All good", http_status_code=201
        )
        payload = json.loads(resp.get_data(as_text=True))
        assert status == 201
        assert payload["status"] == "success"
        assert payload["data"]["foo"] == "bar"
        assert payload["message"] == "All good"
        assert "timestamp" in payload["meta"]
        assert "request_id" in payload["meta"]


def test_security_error_response_schema(app):
    """error_response should return a uniform envelope with error details."""
    with app.test_request_context("/"):
        resp, status = security_utils.error_response(
            code="E_TEST",
            message="Something went wrong",
            http_status_code=418,
            data={"context": "unit-test"},
        )
        payload = json.loads(resp.get_data(as_text=True))
        assert status == 418
        assert payload["status"] == "error"
        assert payload["error"]["code"] == "E_TEST"
        assert payload["error"]["message"] == "Something went wrong"
        assert payload["data"]["context"] == "unit-test"
        assert "timestamp" in payload["meta"]
        assert "request_id" in payload["meta"]


def test_security_log_mfa_attempt_logs_metadata(caplog, app):
    """log_mfa_attempt should log user metadata without exposing MFA codes."""

    class DummyUser:
        id = 123
        email = "test@example.com"

    with app.test_request_context("/"):
        caplog.set_level(logging.INFO)
        security_utils.log_mfa_attempt(DummyUser(), "sms", None)

        log_messages = [rec.getMessage() for rec in caplog.records]
        # Ensure log contains expected markers
        assert any("MFA code generated" in msg for msg in log_messages)
        assert any("sms" in msg for msg in log_messages)
        # Ensure no sensitive code values are leaked
        assert all("code=" not in msg.lower() for msg in log_messages)


def test_security_csrf_protect_enabled(app):
    """Ensure CSRFProtect has been initialized and csrf_token is available in templates."""
    assert "csrf_token" in app.jinja_env.globals
