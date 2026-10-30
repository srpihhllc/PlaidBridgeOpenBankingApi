# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_subscriber_update.py

"""
Smoke test for the subscriber profile update endpoint.

The endpoint currently persists:

    - first_name
    - last_name
    - primary_phone
    - business_phone

Other dashboard fields are intentionally ignored until implemented.
"""

from __future__ import annotations

import re

from flask import url_for
from werkzeug.security import generate_password_hash


def _extract_csrf(response_data: bytes) -> str | None:
    """Extract a rendered csrf_token input from an HTML response."""

    try:
        html = response_data.decode("utf-8")
    except Exception:
        html = str(response_data)

    match = re.search(
        r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']',
        html,
    )

    return match.group(1) if match else None


def _get_csrf_token(client) -> str:
    """
    Obtain a CSRF token from an available rendered page.

    Authenticated pages are preferred. The registration page is used as a
    public fallback.
    """

    app = client.application
    known_endpoints = {
        rule.endpoint for rule in app.url_map.iter_rules()
    }

    candidates: list[str] = []

    for endpoint in (
        "auth.me_dashboard",
        "main.dashboard",
        "sub_ui.sub_index",
    ):
        if endpoint not in known_endpoints:
            continue

        with app.test_request_context():
            candidates.append(url_for(endpoint))

    candidates.append("/")

    for path in candidates:
        response = client.get(path)

        if response.status_code != 200:
            continue

        token = _extract_csrf(response.data)
        if token:
            return token

    with app.test_request_context():
        fallback_url = url_for("auth.register_subscriber")

    response = client.get(fallback_url)
    token = _extract_csrf(response.data)

    assert token, (
        "Could not extract a CSRF token from any candidate page. "
        "Ensure CSRF is enabled correctly and that a rendered form "
        "contains a csrf_token input."
    )

    return token


def test_subscriber_update_smoke(client, db, user_factory):
    """Verify that supported subscriber profile fields are persisted."""

    test_password = "Password123!"
    user = user_factory(
        role="subscriber",
        password=test_password,
    )

    if not getattr(user, "password_hash", None):
        user.password_hash = generate_password_hash(test_password)
        db.session.add(user)
        db.session.commit()

    login_response = client.post(
        url_for("auth.login"),
        data={
            "email": user.email,
            "password": test_password,
        },
        follow_redirects=False,
    )

    assert login_response.status_code in (200, 302), (
        "Login failed with status "
        f"{login_response.status_code}: "
        f"{login_response.data.decode('utf-8', errors='replace')[:500]}"
    )

    if login_response.status_code == 302:
        redirect_location = login_response.headers.get("Location")
        assert redirect_location, "Login returned a redirect without Location"
        client.get(redirect_location, follow_redirects=False)

    csrf_token = _get_csrf_token(client)

    expected_primary_phone = "5551234567"
    expected_business_phone = "9015551212"

    payload = {
        "csrf_token": csrf_token,
        "primary_phone": expected_primary_phone,
        "business_phone": expected_business_phone,
        "first_name": "Smoke",
        "last_name": "Test",

        # These fields are currently ignored by the handler.
        "subscriber_id": str(getattr(user, "id", "")),
        "ssn_last4": "1234",
        "phone": "5551234567",
        "bank_name": "Test Bank",
        "routing_number": "111000025",
        "account_ending": "6789",
        "business_address": "1 Test Way",
        "ein": "12-3456789",
        "business_city": "Memphis",
        "business_state": "TN",
        "business_zip": "38103",
        "home_address": "123 Home St",
        "same_address_flag": "true",
        "password": "",
    }

    post_response = client.post(
        url_for("subscriber.update_profile"),
        data=payload,
        follow_redirects=False,
    )

    assert post_response.status_code == 302, (
        "Expected update_profile to redirect after a successful update. "
        f"Got status {post_response.status_code}. "
        f"Location={post_response.headers.get('Location')!r}. "
        f"Body={post_response.data.decode('utf-8', errors='replace')[:500]}"
    )

    location = post_response.headers.get("Location", "")
    assert location, "update_profile returned a redirect without Location"
    assert "/auth/login" not in location, (
        "update_profile redirected to login; the authenticated session was "
        "not available to the update request"
    )

    db.session.expire_all()
    updated_user = db.session.get(type(user), user.id)

    assert updated_user is not None

    actual_primary_phone = getattr(updated_user, "primary_phone", None) or ""
    assert actual_primary_phone.endswith("4567"), (
        "Expected user.primary_phone to end with '4567', "
        f"got {actual_primary_phone!r}"
    )

    actual_business_phone = (
        getattr(updated_user, "business_phone", None) or ""
    )
    assert actual_business_phone.endswith("1212"), (
        "Expected user.business_phone to end with '1212', "
        f"got {actual_business_phone!r}"
    )

    assert getattr(updated_user, "account_ending", None) != "6789", (
        "account_ending was unexpectedly persisted even though it is not "
        "supported by the current handler"
    )
