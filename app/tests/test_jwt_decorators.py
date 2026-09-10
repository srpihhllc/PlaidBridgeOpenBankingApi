# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_jwt_decorators.py

from unittest.mock import MagicMock, patch

import pytest
from flask import jsonify
from flask_jwt_extended import create_access_token
from flask_jwt_extended.exceptions import (
    JWTExtendedException,
    NoAuthorizationError,
    RevokedTokenError,
)

from app.decorators.jwt import admin_required, roles_required


def test_admin_required_decorator_success(app):
    """Test @admin_required decorator with a valid bearer token."""

    @admin_required
    def dummy_admin_view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        admin_token = create_access_token(
            identity="admin_user",
            additional_claims={"role": "admin", "roles": ["admin"]},
        )

    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.roles = ["admin"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {admin_token}"}
        ):
            res, status = dummy_admin_view()
            assert status == 200
            assert res.get_json() == {"status": "ok"}


def test_roles_required_decorator_multi_role(app):
    """Test @roles_required with multiple allowed roles (or-condition)."""

    @roles_required("admin", "editor", "analyst")
    def multi_role_view():
        return jsonify({"status": "authorized"}), 200

    with app.app_context():
        # User only has one of the allowed roles ('editor')
        editor_token = create_access_token(
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
            "/", headers={"Authorization": f"Bearer {editor_token}"}
        ):
            res, status = multi_role_view()
            assert status == 200
            assert res.get_json() == {"status": "authorized"}


def test_jwt_decorators_fresh_token(app):
    """Test token validation when fresh=True is explicitly set."""

    @roles_required("admin")
    def fresh_token_view():
        return jsonify({"status": "fresh_ok"}), 200

    with app.app_context():
        fresh_token = create_access_token(
            identity="admin_user",
            fresh=True,
            additional_claims={"role": "admin", "roles": ["admin"]},
        )

    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.roles = ["admin"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {fresh_token}"}
        ):
            res, status = fresh_token_view()
            assert status == 200
            assert res.get_json() == {"status": "fresh_ok"}


def test_jwt_decorators_missing_claims(app):
    """Test decorator handling when JWT is missing required role claims."""

    @roles_required("admin")
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        # Token issued without 'role' or 'roles' claims
        token_no_claims = create_access_token(identity="basic_user")

    mock_user = MagicMock()
    mock_user.role = None
    mock_user.roles = []

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token_no_claims}"}
        ):
            response = protected_view()
            # Expecting access.py unified_roles_required to return a 403 response
            if isinstance(response, tuple):
                assert response[1] == 403
            else:
                assert response.status_code == 403


def test_jwt_decorators_malformed_header(app):
    """Test request handling with a malformed/garbage JWT string."""

    @admin_required
    def protected_view():
        return jsonify({"status": "ok"}), 200

    # Malformed bearer token
    with app.test_request_context(
        "/", headers={"Authorization": "Bearer invalid.jwt.string"}
    ):
        try:
            protected_view()
            assert False, "Expected JWTExtendedException on malformed token"
        except Exception as e:
            assert isinstance(
                e, JWTExtendedException
            ) or e.__class__.__name__ in (
                "DecodeError",
                "InvalidTokenError",
            )


def test_jwt_decorators_missing_header(app):
    """Test request handling when no Authorization header is passed."""

    @admin_required
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.test_request_context("/"):
        try:
            protected_view()
            assert False, "Expected NoAuthorizationError when missing token"
        except Exception as e:
            assert (
                isinstance(e, (NoAuthorizationError, JWTExtendedException))
                or e.__class__.__name__ == "Unauthorized"
            )


def test_jwt_decorators_revoked_token(app):
    """Test request handling when token blocklist callback rejects the JWT."""

    @admin_required
    def protected_view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="admin_user",
            additional_claims={"role": "admin", "roles": ["admin"]},
        )

    # Patch the verifier symbol imported into app.decorators.jwt so the decorator
    # raises RevokedTokenError before the library attempts user lookup.
    with patch(
        "app.decorators.jwt.verify_jwt_in_request",
        side_effect=RevokedTokenError(
            jwt_header={"alg": "HS256", "typ": "JWT"},
            jwt_data={"sub": "admin_user"},
        ),
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            with pytest.raises(RevokedTokenError):
                protected_view()
