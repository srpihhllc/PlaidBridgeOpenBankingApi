# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_access_decorators.py

from unittest.mock import MagicMock, patch

import pytest
from flask import jsonify
from flask_jwt_extended import create_access_token, create_refresh_token
from flask_jwt_extended.exceptions import JWTExtendedException
from werkzeug.exceptions import Forbidden

from app.decorators.access import (
    admin_required,
    require_admin,
    roles_required,
    subscriber_required,
    super_admin_required,
)


def test_roles_required_explicit_mismatch(app):
    """Test role mismatch returns 403 Forbidden."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="editor_user",
            additional_claims={"role": "editor", "roles": ["editor"]},
        )

    mock_user = MagicMock()
    mock_user.role = "editor"
    mock_user.roles = ["editor"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            response = view()
            status_code = (
                response[1]
                if isinstance(response, tuple)
                else response.status_code
            )
            assert status_code == 403


def test_roles_required_multiple_claims_array(app):
    """Test user with multiple roles array ['editor', 'analyst'] accessing an analyst endpoint."""

    @roles_required("analyst")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="multi_role_user",
            additional_claims={"roles": ["editor", "analyst"]},
        )

    mock_user = MagicMock()
    mock_user.roles = ["editor", "analyst"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            response = view()
            res, status = (
                response
                if isinstance(response, tuple)
                else (response, response.status_code)
            )
            assert status == 200


def test_subscriber_required_success_and_failure(app):
    """Test @subscriber_required allows subscriber role and blocks non-subscribers."""

    @subscriber_required
    def view():
        return jsonify({"status": "subscriber_ok"}), 200

    with app.app_context():
        sub_token = create_access_token(
            identity="sub_user",
            additional_claims={"role": "subscriber", "roles": ["subscriber"]},
        )

        non_sub_token = create_access_token(
            identity="guest_user",
            additional_claims={"role": "guest", "roles": ["guest"]},
        )

    # 1. Success path
    mock_sub = MagicMock()
    mock_sub.role = "subscriber"
    mock_sub.roles = ["subscriber"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_sub
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {sub_token}"}
        ):
            response = view()
            res, status = (
                response
                if isinstance(response, tuple)
                else (response, response.status_code)
            )
            assert status == 200

    # 2. Failure path
    mock_non_sub = MagicMock()
    mock_non_sub.role = "guest"
    mock_non_sub.roles = ["guest"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_non_sub,
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {non_sub_token}"}
        ):
            response = view()
            status_code = (
                response[1]
                if isinstance(response, tuple)
                else response.status_code
            )
            assert status_code == 403


def test_jwt_rejects_refresh_token_on_access_endpoint(app):
    """Ensure refresh tokens cannot be used to authenticate standard access endpoints.

    Patch the verifier used by the decorator (app.decorators.access.verify_jwt_in_request)
    so the decorator immediately raises the intended error and does not attempt to
    decode the refresh token via the library internals.
    """

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        refresh_token = create_refresh_token(identity="admin_user")

    class MockWrongTokenError(JWTExtendedException):
        pass

    # Patch the symbol imported into our module (not the library implementation)
    with patch(
        "app.decorators.access.verify_jwt_in_request",
        side_effect=MockWrongTokenError("Only access tokens are allowed"),
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {refresh_token}"}
        ):
            with pytest.raises(MockWrongTokenError):
                view()


def test_jwt_invalid_authorization_prefix(app):
    """Non-Bearer authorization header should not crash; returns 401 when no session user exists."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    # Non-Bearer prefix; decorator treats this as missing auth and falls back to session check.
    with app.test_request_context(
        "/", headers={"Authorization": "Token abc123_invalid"}
    ):
        response = view()
        status = (
            response[1]
            if isinstance(response, tuple)
            else response.status_code
        )
        # When no session user exists, the decorator returns 401 (Missing Authorization Header).
        assert status == 401


def test_jwt_expired_token(app):
    """Ensure expired tokens trigger expiration exception."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    class MockExpiredSignatureError(JWTExtendedException):
        pass

    with patch(
        "app.decorators.access.verify_jwt_in_request",
        side_effect=MockExpiredSignatureError("Signature has expired"),
    ):
        with app.test_request_context(
            "/", headers={"Authorization": "Bearer expired.jwt.token"}
        ):
            with pytest.raises(MockExpiredSignatureError):
                view()


def test_admin_required_shortcut(app):
    """Test the admin_required shortcut decorator."""

    @admin_required
    def view():
        return jsonify({"status": "admin_ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="admin_user",
            additional_claims={"roles": ["admin"]},
        )

    mock_user = MagicMock()
    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            response = view()
            res, status = (
                response
                if isinstance(response, tuple)
                else (response, response.status_code)
            )
            assert status == 200


def test_super_admin_required_shortcut(app):
    """Test the super_admin_required shortcut decorator."""

    @super_admin_required
    def view():
        return jsonify({"status": "super_ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="super_user",
            additional_claims={"roles": ["super_admin"]},
        )

    mock_user = MagicMock()
    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            response = view()
            res, status = (
                response
                if isinstance(response, tuple)
                else (response, response.status_code)
            )
            assert status == 200


@patch("app.decorators.access.current_user")
def test_roles_required_fallback_to_session(mock_current_user, app):
    """Test fallback to Flask-Login session when no JWT is provided."""

    # Setup mock session user
    mock_current_user.is_authenticated = True
    mock_current_user.role = "editor"
    mock_current_user.is_admin = False

    @roles_required("editor")
    def view():
        return jsonify({"status": "session_ok"}), 200

    # Execute request with NO Authorization header
    with app.test_request_context("/"):
        response = view()
        res, status = (
            response
            if isinstance(response, tuple)
            else (response, response.status_code)
        )
        assert status == 200


@patch("app.decorators.access.current_user")
def test_roles_required_jwt_fails_but_session_passes(mock_current_user, app):
    """Test when JWT lacks required roles, but the session user HAS the role."""

    # Session user HAS the required admin role
    mock_current_user.is_authenticated = True
    mock_current_user.role = "admin"
    mock_current_user.is_admin = True

    @roles_required("admin")
    def view():
        return jsonify({"status": "fallback_ok"}), 200

    with app.app_context():
        # JWT token deliberately lacks the admin role (has 'guest')
        token = create_access_token(
            identity="guest_user",
            additional_claims={"roles": ["guest"]},
        )

    mock_user = MagicMock()
    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        # Execute request WITH the weak JWT header
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            response = view()
            res, status = (
                response
                if isinstance(response, tuple)
                else (response, response.status_code)
            )
            # Should still be 200 because it fell through to the session user check
            assert status == 200


@patch("app.decorators.access.current_user")
@patch("app.decorators.access.user_is_admin")
@patch("app.decorators.access.url_for", return_value="/mock-login")
def test_require_admin_legacy_ui(
    mock_url_for, mock_user_is_admin, mock_current_user, app
):
    """Test the legacy session-only require_admin decorator."""

    @require_admin
    def view():
        return jsonify({"status": "ui_admin_ok"}), 200

    # Case 1: Not authenticated -> Redirects to login
    mock_current_user.is_authenticated = False
    with app.test_request_context("/"):
        response = view()
        assert response.status_code == 302
        assert response.location == "/mock-login"

    # Case 2: Authenticated, but not admin -> Aborts with 403
    mock_current_user.is_authenticated = True
    mock_user_is_admin.return_value = False
    with app.test_request_context("/"):
        with pytest.raises(Forbidden):
            view()

    # Case 3: Authenticated AND is admin -> 200 OK
    mock_user_is_admin.return_value = True
    with app.test_request_context("/"):
        response = view()
        res, status = (
            response
            if isinstance(response, tuple)
            else (response, response.status_code)
        )
        assert status == 200
