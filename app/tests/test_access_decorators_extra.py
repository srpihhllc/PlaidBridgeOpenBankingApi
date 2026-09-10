# app/tests/test_access_decorators_extra.py

from unittest.mock import MagicMock, patch
from flask import jsonify
from flask_jwt_extended import create_access_token

from app.decorators.access import (
    user_is_admin,
    roles_required,
    require_admin,
)


# ----------------------------------------------------------------------
# Covers lines 14–18: user_is_admin secondary role checks
# ----------------------------------------------------------------------
def test_user_is_admin_role_only_no_is_admin():
    """user_is_admin should return True when current_user.role == 'admin' even if is_admin is missing."""
    fake_user = MagicMock()
    if hasattr(fake_user, "is_admin"):
        delattr(fake_user, "is_admin")
    fake_user.role = "admin"

    with patch("app.decorators.access.current_user", fake_user):
        assert user_is_admin() is True


# ----------------------------------------------------------------------
# Covers line 62: roles claim is a single string
# ----------------------------------------------------------------------
def test_roles_required_roles_claim_single_string(app):
    """roles_required should normalize roles='admin' into ['admin']."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="single_role_user",
            additional_claims={"roles": "admin"},
        )

    mock_user = MagicMock()
    mock_user.roles = ["admin"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            res, status = view()
            assert status == 200


# ----------------------------------------------------------------------
# Covers line 65: role claim exists but roles missing
# ----------------------------------------------------------------------
def test_roles_required_role_claim_only(app):
    """roles_required should accept single 'role' claim when 'roles' is absent."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="role_only_user",
            additional_claims={"role": "admin"},
        )

    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.roles = []

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        with app.test_request_context(
            "/", headers={"Authorization": f"Bearer {token}"}
        ):
            res, status = view()
            assert status == 200


# ----------------------------------------------------------------------
# Covers lines 54–56: generic except Exception safety catch
# ----------------------------------------------------------------------
def test_roles_required_generic_exception_falls_back_to_session(app):
    """If verify_jwt_in_request raises a non-JWT Exception, fallback to session should occur."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with patch(
        "app.decorators.access.verify_jwt_in_request",
        side_effect=Exception("boom"),
    ):
        fake_user = MagicMock()
        fake_user.is_authenticated = True
        fake_user.role = "admin"
        fake_user.roles = ["admin"]

        with patch("app.decorators.access.current_user", fake_user):
            with app.test_request_context("/"):
                res, status = view()
                assert status == 200


# ----------------------------------------------------------------------
# Covers line 86: JWT verified but no matching role AND session user unauthenticated
# ----------------------------------------------------------------------
def test_roles_required_jwt_verified_no_match_and_no_session(app):
    """JWT verified but no matching role AND no session user -> 403 Forbidden."""

    @roles_required("admin")
    def view():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        token = create_access_token(
            identity="guest_user",
            additional_claims={"roles": ["guest"]},
        )

    mock_user = MagicMock()
    mock_user.roles = ["guest"]

    with patch(
        "flask_jwt_extended.view_decorators._load_user", return_value=mock_user
    ):
        fake_session = MagicMock()
        fake_session.is_authenticated = False

        with patch("app.decorators.access.current_user", fake_session):
            with app.test_request_context(
                "/", headers={"Authorization": f"Bearer {token}"}
            ):
                response = view()
                status = (
                    response[1]
                    if isinstance(response, tuple)
                    else response.status_code
                )
                assert status == 403


# ----------------------------------------------------------------------
# Covers lines 125–126: require_admin fallback redirect to /mock-login
# ----------------------------------------------------------------------
def test_require_admin_url_for_raises_redirects_to_mock_login(app):
    """require_admin should redirect to /mock-login when url_for raises an exception."""

    @require_admin
    def view():
        return jsonify({"status": "ui_ok"}), 200

    fake_user = MagicMock()
    fake_user.is_authenticated = False

    with (
        patch("app.decorators.access.current_user", fake_user),
        patch(
            "app.decorators.access.url_for",
            side_effect=Exception("routing error"),
        ),
    ):
        with app.test_request_context("/"):
            response = view()
            assert response.status_code == 302
            assert response.location == "/mock-login"
