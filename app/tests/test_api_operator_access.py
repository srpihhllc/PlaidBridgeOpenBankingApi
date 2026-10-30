# =============================================================================
# FILE: app/tests/test_api_operator_access.py
# DESCRIPTION:
#     - Unit tests for PlaidBridge operator and subscriber access control guards.
#     - Validates safe observability vs dangerous operation step-up separation.
# =============================================================================

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

from app.blueprints import api_routes
from app.constants import OPERATOR_MODE_KEY


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    return app


def check_safe_operator(
    app,
    monkeypatch,
    *,
    role="creator",
    authenticated=True,
    permission=False,
    operator_session=False,
    is_admin=False,
):
    user = SimpleNamespace(
        role=role,
        is_authenticated=authenticated,
        is_admin=is_admin,
        id=123,
    )

    monkeypatch.setattr(api_routes, "current_user", user)
    monkeypatch.setattr(
        api_routes,
        "has_permission",
        lambda checked_user, requested: (
            checked_user is user
            and requested == "read_operational_data"
            and permission
        ),
    )

    with app.test_request_context("/"):
        if operator_session:
            api_routes.session[OPERATOR_MODE_KEY] = True

        return api_routes._require_safe_operator()


def test_creator_role_alone_does_not_grant_operator_access(app, monkeypatch):
    user, error = check_safe_operator(app, monkeypatch)

    assert user is None
    assert error is not None

    _, status_code = error
    assert status_code == 403


def test_operational_permission_grants_creator_operator_access(
    app, monkeypatch
):
    user, error = check_safe_operator(app, monkeypatch, permission=True)

    assert user is not None
    assert error is None


def test_operator_mode_session_grants_creator_operator_access(
    app, monkeypatch
):
    user, error = check_safe_operator(
        app,
        monkeypatch,
        operator_session=True,
    )

    assert user is not None
    assert error is None


def test_unauthenticated_user_is_denied_even_with_operator_session(
    app, monkeypatch
):
    user, error = check_safe_operator(
        app,
        monkeypatch,
        authenticated=False,
        operator_session=True,
    )

    assert user is None
    assert error is not None

    _, status_code = error
    assert status_code == 401


def test_owner_bypasses_safe_operator_guard(app, monkeypatch):
    user, error = check_safe_operator(app, monkeypatch, is_admin=True)

    assert user is not None
    assert error is None


def test_owner_denied_dangerous_without_operator_mode(app, monkeypatch):
    user = SimpleNamespace(
        role="admin",
        is_authenticated=True,
        is_admin=True,
        id=123,
    )
    monkeypatch.setattr(api_routes, "current_user", user)

    with app.test_request_context("/api/operator/debug_flags", method="POST"):
        # Without operator session elevation, dangerous actions fail
        res_user, error = api_routes._require_dangerous_operator()
        assert res_user is None
        assert error is not None
        _, status_code = error
        assert status_code == 403


@patch("app.services.god_mode_audit_service.GodModeAuditService.log")
def test_owner_allowed_dangerous_with_operator_mode(mock_audit_log, app, monkeypatch):
    user = SimpleNamespace(
        role="admin",
        is_authenticated=True,
        is_admin=True,
        id=123,
    )
    monkeypatch.setattr(api_routes, "current_user", user)

    with app.test_request_context("/api/operator/debug_flags", method="POST"):
        api_routes.session[OPERATOR_MODE_KEY] = True

        res_user, error = api_routes._require_dangerous_operator()
        assert res_user is not None
        assert error is None
        
        # Verify compliance audit log was recorded
        mock_audit_log.assert_called_once()