# =============================================================================
# FILE: app/tests/test_jwt_decorators.py
# =============================================================================

from unittest.mock import MagicMock, patch

from flask import jsonify
from flask_jwt_extended import create_access_token
from flask_jwt_extended.exceptions import (
    JWTExtendedException,
    NoAuthorizationError,
    RevokedTokenError,
)

from app.decorators.jwt import admin_required, roles_required


def _assert_auth_failure(result):
    """
    Helper that accepts common auth failure responses.
    """
    if isinstance(result, tuple):
        status = result[1]
        assert status in (401, 403, 422)
    else:
        assert result.status_code in (401, 403, 422)


# =============================================================================
# SUCCESS PATHS
# =============================================================================


def test_admin_required_decorator_success(app):
    """Test @admin_required decorator with a valid bearer token."""

    @admin_required
    def dummy_admin_view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        admin_token = create_access_token(
            identity="admin_user",
            additional_claims={
                "role": "admin",
                "roles": ["admin"],
            },
        )

    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.roles = ["admin"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={
                "Authorization": f"Bearer {admin_token}",
            },
        ):
            response, status = dummy_admin_view()

            assert status == 200
            assert response.get_json() == {"status": "ok"}


def test_roles_required_decorator_multi_role(app):
    """Test @roles_required with multiple allowed roles."""

    @roles_required("admin", "editor", "analyst")
    def multi_role_view():
        return jsonify({"status": "authorized"}), 200

    with app.app_context():
        editor_token = create_access_token(
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
            headers={
                "Authorization": f"Bearer {editor_token}",
            },
        ):
            response, status = multi_role_view()

            assert status == 200
            assert response.get_json() == {
                "status": "authorized",
            }


def test_jwt_decorators_fresh_token(app):
    """Test token validation when fresh=True is explicitly set."""

    @roles_required("admin")
    def fresh_token_view():
        return jsonify({"status": "fresh_ok"}), 200

    with app.app_context():
        fresh_token = create_access_token(
            identity="admin_user",
            fresh=True,
            additional_claims={
                "role": "admin",
                "roles": ["admin"],
            },
        )

    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.roles = ["admin"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={
                "Authorization": f"Bearer {fresh_token}",
            },
        ):
            response, status = fresh_token_view()

            assert status == 200
            assert response.get_json() == {
                "status": "fresh_ok",
            }


# =============================================================================
# AUTHORIZATION FAILURES
# =============================================================================


def test_jwt_decorators_missing_claims(app):
    """Test handling when JWT is missing required role claims."""

    @roles_required("admin")
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token_no_claims = create_access_token(
            identity="basic_user",
        )

    mock_user = MagicMock()
    mock_user.role = None
    mock_user.roles = []

    with patch(
        "flask_jwt_extended.view_decorators._load_user",
        return_value=mock_user,
    ):
        with app.test_request_context(
            "/",
            headers={
                "Authorization": f"Bearer {token_no_claims}",
            },
        ):
            result = protected_view()

            _assert_auth_failure(result)


# =============================================================================
# JWT FAILURE PATHS
# =============================================================================


def test_jwt_decorators_malformed_header(app):
    """
    Test malformed JWT input.

    Supports both:
    1. Exception-raising implementations.
    2. Response-returning implementations.
    """

    @admin_required
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.test_request_context(
        "/",
        headers={
            "Authorization": "Bearer invalid.jwt.string",
        },
    ):
        try:
            result = protected_view()
            _assert_auth_failure(result)

        except Exception as exc:
            assert (
                isinstance(exc, JWTExtendedException)
                or exc.__class__.__name__
                in (
                    "DecodeError",
                    "InvalidTokenError",
                )
            )


def test_jwt_decorators_missing_header(app):
    """
    Test request handling without Authorization header.

    Supports both:
    1. Exception-raising implementations.
    2. Response-returning implementations.
    """

    @admin_required
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.test_request_context("/"):
        try:
            result = protected_view()
            _assert_auth_failure(result)

        except Exception as exc:
            assert (
                isinstance(
                    exc,
                    (
                        NoAuthorizationError,
                        JWTExtendedException,
                    ),
                )
                or exc.__class__.__name__ == "Unauthorized"
            )


def test_jwt_decorators_revoked_token(app):
    """
    Test revoked-token handling.

    Supports both:
    1. Decorator raises RevokedTokenError.
    2. Decorator converts the failure into a Flask response.
    """

    @admin_required
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="admin_user",
            additional_claims={
                "role": "admin",
                "roles": ["admin"],
            },
        )

    with patch(
        "app.decorators.jwt.verify_jwt_in_request",
        side_effect=RevokedTokenError(
            jwt_header={
                "alg": "HS256",
                "typ": "JWT",
            },
            jwt_data={
                "sub": "admin_user",
            },
        ),
    ):
        with app.test_request_context(
            "/",
            headers={
                "Authorization": f"Bearer {token}",
            },
        ):
            try:
                result = protected_view()
                _assert_auth_failure(result)

            except Exception as exc:
                assert isinstance(
                    exc,
                    (
                        RevokedTokenError,
                        JWTExtendedException,
                    ),
                )