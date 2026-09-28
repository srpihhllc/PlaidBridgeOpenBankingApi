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


def _get_status_code(response):
    """Return the status code from either a Flask response or response tuple."""
    return (
        response[1]
        if isinstance(response, tuple)
        else response.status_code
    )


def test_roles_required_explicit_mismatch(app):
    """Test role mismatch returns 403 Forbidden."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="editor_user",
            additional_claims={
                "role": "editor",
                "roles": ["editor"],
            },
        )

    mock_user = MagicMock()
    mock_user.role = "editor"
    mock_user.roles = ["editor"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {token}"},
        ):
            response = view()

    assert _get_status_code(response) == 403


def test_roles_required_multiple_claims_array(app):
    """Test a user with multiple roles can access a matching endpoint."""

    @roles_required("analyst")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="multi_role_user",
            additional_claims={
                "roles": ["editor", "analyst"],
            },
        )

    mock_user = MagicMock()
    mock_user.roles = ["editor", "analyst"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {token}"},
        ):
            response = view()

    assert _get_status_code(response) == 200


def test_subscriber_required_success_and_failure(app):
    """Test subscriber access succeeds and non-subscriber access fails."""

    @subscriber_required
    def view():
        return jsonify({"status": "subscriber_ok"}), 200

    with app.app_context():
        subscriber_token = create_access_token(
            identity="sub_user",
            additional_claims={
                "role": "subscriber",
                "roles": ["subscriber"],
            },
        )

        non_subscriber_token = create_access_token(
            identity="guest_user",
            additional_claims={
                "role": "guest",
                "roles": ["guest"],
            },
        )

    subscriber_user = MagicMock()
    subscriber_user.role = "subscriber"
    subscriber_user.roles = ["subscriber"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=subscriber_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {subscriber_token}"},
        ):
            response = view()

    assert _get_status_code(response) == 200

    non_subscriber_user = MagicMock()
    non_subscriber_user.role = "guest"
    non_subscriber_user.roles = ["guest"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=non_subscriber_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {non_subscriber_token}"},
        ):
            response = view()

    assert _get_status_code(response) == 403


def test_jwt_rejects_refresh_token_on_access_endpoint(app):
    """Ensure refresh tokens are rejected by access-only endpoints."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        refresh_token = create_refresh_token(identity="admin_user")

    class MockWrongTokenError(JWTExtendedException):
        pass

    with patch(
        "app.decorators.access.verify_jwt_in_request",
        side_effect=MockWrongTokenError("Only access tokens are allowed"),
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {refresh_token}"},
        ):
            with pytest.raises(MockWrongTokenError):
                view()


def test_jwt_invalid_authorization_prefix(app):
    """Test that a non-Bearer authorization header returns 401."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.test_request_context(
        "/",
        headers={"Authorization": "Token abc123_invalid"},
    ):
        response = view()

    assert _get_status_code(response) == 401


def test_jwt_expired_token(app):
    """Ensure expired tokens raise the expected exception."""

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
            "/",
            headers={"Authorization": "Bearer expired.jwt.token"},
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
            additional_claims={
                "roles": ["admin"],
            },
        )

    mock_user = MagicMock()

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {token}"},
        ):
            response = view()

    assert _get_status_code(response) == 200


def test_super_admin_required_shortcut(app):
    """Test the super_admin_required shortcut decorator."""

    @super_admin_required
    def view():
        return jsonify({"status": "super_ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="super_user",
            additional_claims={
                "roles": ["super_admin"],
            },
        )

    mock_user = MagicMock()

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {token}"},
        ):
            response = view()

    assert _get_status_code(response) == 200


@patch("app.decorators.access.current_user")
def test_roles_required_fallback_to_session(mock_current_user, app):
    """Test fallback to Flask-Login when no JWT is provided."""

    mock_current_user.is_authenticated = True
    mock_current_user.role = "editor"
    mock_current_user.is_admin = False

    @roles_required("editor")
    def view():
        return jsonify({"status": "session_ok"}), 200

    with app.test_request_context("/"):
        response = view()

    assert _get_status_code(response) == 200


@patch("app.decorators.access.current_user")
def test_roles_required_jwt_fails_but_session_passes(mock_current_user, app):
    """Test that a valid session role can satisfy a failed JWT role check."""

    mock_current_user.is_authenticated = True
    mock_current_user.role = "admin"
    mock_current_user.is_admin = True

    @roles_required("admin")
    def view():
        return jsonify({"status": "fallback_ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="guest_user",
            additional_claims={
                "roles": ["guest"],
            },
        )

    mock_user = MagicMock()

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={"Authorization": f"Bearer {token}"},
        ):
            response = view()

    assert _get_status_code(response) == 200


@patch("app.decorators.access.current_user")
@patch("app.decorators.access.user_is_admin")
@patch("app.decorators.access.url_for", return_value="/mock-login")
def test_require_admin_legacy_ui(
    mock_url_for,
    mock_user_is_admin,
    mock_current_user,
    app,
):
    """Test the legacy session-only require_admin decorator."""

    @require_admin
    def view():
        return jsonify({"status": "ui_admin_ok"}), 200

    # Unauthenticated users are redirected to the login page.
    mock_current_user.is_authenticated = False
    mock_user_is_admin.return_value = False

    with app.test_request_context("/"):
        response = view()

    assert response.status_code == 302
    assert response.location == "/mock-login"

    # Authenticated non-admin users receive a 403 response.
    mock_current_user.is_authenticated = True
    mock_user_is_admin.return_value = False

    with app.test_request_context("/"):
        with pytest.raises(Forbidden):
            view()

    # Authenticated administrators can access the endpoint.
    mock_user_is_admin.return_value = True

    with app.test_request_context("/"):
        response = view()

    assert _get_status_code(response) == 200
