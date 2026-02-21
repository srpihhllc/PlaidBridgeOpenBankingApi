# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/test_admin_logout.py

import pytest


@pytest.mark.auth
def test_admin_logout(client, db_session):
    """
    End-to-end smoke test: seeded admin can log out successfully.
    """

    # Use seeded admin credentials
    email = "srpollardsihhllc@gmail.com"
    password = "NunuMiermier12$t"

    # Log in first
    login_response = client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
    assert login_response.status_code == 200
    assert b"Logged in successfully" in login_response.data or b"Dashboard" in login_response.data

    # Now log out
    logout_response = client.get("/auth/logout", follow_redirects=True)
    assert logout_response.status_code == 200
    assert b"Logged out" in logout_response.data or b"Login" in logout_response.data
