# home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/test_admin_login.py

import pytest


@pytest.mark.auth
def test_admin_login(client, db_session):
    """
    End-to-end smoke test: seeded admin can log in successfully.
    """

    # Use seeded admin credentials
    email = "srpollardsihhllc@gmail.com"
    password = "NunuMiermier12$t"

    # Post to login route
    response = client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )

    # Assert login succeeded
    assert response.status_code == 200, "Login request must return 200 OK"
    assert (
        b"Logged in successfully" in response.data or b"Dashboard" in response.data
    ), "Login response must indicate success"
