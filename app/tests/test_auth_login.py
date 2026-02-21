# =============================================================================
# FILE: app/tests/test_auth_login.py
# DESCRIPTION: Tests for login flow with different user roles and MFA states.
# =============================================================================

import pytest
from flask import url_for
from werkzeug.security import generate_password_hash

from app.models import User


@pytest.fixture
def test_user(db_session):
    """Create a baseline user with no role and no MFA."""
    user = User(
        email="norole@example.com",
        password_hash=generate_password_hash("password123"),
        role=None,
        is_admin=False,
        mfa_enabled=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_login_with_none_role(client, test_user):
    """Ensure login works when user.role is None → redirect to sub_ui."""
    # ✅ Build URL inside a request context
    with client.application.test_request_context():
        login_url = url_for("auth.login")
        sub_index_url = url_for("sub_ui.sub_index")

    resp = client.post(
        login_url,
        data={"email": test_user.email, "password": "password123"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert sub_index_url in resp.headers["Location"]


def test_login_with_admin_role(client, db_session):
    """Ensure role='admin' redirects to admin UI."""
    admin = User(
        email="admin_test@example.com",  # ✅ avoid collision with seeded admin@example.com
        password_hash=generate_password_hash("password123"),
        role="admin",
        is_admin=True,  # ✅ match your app logic
        mfa_enabled=False,
    )
    db_session.add(admin)
    db_session.commit()

    with client.application.test_request_context():
        login_url = url_for("auth.login")
        admin_index_url = url_for("admin.admin_index")  # ✅ correct endpoint

    resp = client.post(
        login_url,
        data={"email": admin.email, "password": "password123"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert admin_index_url in resp.headers["Location"]


def test_login_with_is_admin_flag(client, db_session):
    """Ensure is_admin=True also redirects to admin UI."""
    admin_flag = User(
        email="flagadmin@example.com",
        password_hash=generate_password_hash("password123"),
        role=None,
        is_admin=True,
        mfa_enabled=False,
    )
    db_session.add(admin_flag)
    db_session.commit()

    with client.application.test_request_context():
        login_url = url_for("auth.login")
        admin_index_url = url_for("admin.admin_index")  # ✅ corrected endpoint

    resp = client.post(
        login_url,
        data={"email": admin_flag.email, "password": "password123"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert admin_index_url in resp.headers["Location"]


def test_login_with_mfa_redirects_to_prompt(client, db_session):
    """Ensure users with MFA enabled are redirected to MFA prompt."""
    mfa_user = User(
        email="mfa@example.com",
        password_hash=generate_password_hash("password123"),
        role=None,
        is_admin=False,
        mfa_enabled=True,
    )
    db_session.add(mfa_user)
    db_session.commit()

    with client.application.test_request_context():
        login_url = url_for("auth.login")
        mfa_prompt_url = url_for("auth.mfa_prompt")

    resp = client.post(
        login_url,
        data={"email": mfa_user.email, "password": "password123"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert mfa_prompt_url in resp.headers["Location"]


def test_login_invalid_credentials(client):
    """Invalid credentials should redirect back to login with flash message."""
    with client.application.test_request_context():
        login_url = url_for("auth.login")

    resp = client.post(
        login_url,
        data={"email": "ghost@example.com", "password": "wrong"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert login_url in resp.headers["Location"]
