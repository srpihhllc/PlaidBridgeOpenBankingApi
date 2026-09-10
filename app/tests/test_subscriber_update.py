# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_subscriber_update.py

# app/tests/test_subscriber_update.py
"""
Smoke test for the subscriber profile update endpoint.

Tests that POST /subscriber/update_profile persists the fields the handler
actually supports — primary_phone and business_phone — to the User row.

Handler source: app/blueprints/subscriber_routes.py
Supported persisted fields: first_name, last_name, primary_phone, business_phone
"""

from __future__ import annotations

import re

from flask import url_for
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_csrf(response_data: bytes) -> str | None:
    """Extract CSRF token value from an HTML response using a simple regex."""
    try:
        html = response_data.decode("utf-8")
    except Exception:
        html = str(response_data)
    m = re.search(
        r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html
    )
    return m.group(1) if m else None


def _get_csrf_token(client) -> str:
    """
    Walk a prioritised list of pages to find one that (a) returns HTTP 200
    and (b) contains a rendered csrf_token input.  Falls back to the
    register-subscriber page which always renders the token even for
    anonymous visitors.
    """
    app = client.application
    known_endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    candidates: list[str] = []
    # Prefer authenticated pages in priority order
    for ep in ("auth.me_dashboard", "main.dashboard", "sub_ui.sub_index"):
        if ep in known_endpoints:
            with app.test_request_context():
                candidates.append(url_for(ep))
    candidates.append("/")

    for path in candidates:
        r = client.get(path)
        if r.status_code == 200 and b"csrf_token" in r.data:
            token = _extract_csrf(r.data)
            if token:
                return token

    # Final fallback: register page is always public and always has a CSRF token
    with app.test_request_context():
        fallback_url = url_for("auth.register_subscriber")
    r = client.get(fallback_url)
    token = _extract_csrf(r.data)
    assert token, (
        "Could not extract a CSRF token from any candidate page. "
        "Ensure WTF_CSRF_ENABLED=True and that at least one rendered form "
        "contains a hidden csrf_token input."
    )
    return token


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_subscriber_update_smoke(client, db, user_factory):
    """
    Smoke test: create a subscriber, sign in, POST an update to
    subscriber.update_profile, and assert the DB-persisted change.

    What the handler actually persists (see subscriber_routes.py):
        first_name, last_name, primary_phone, business_phone

    Fields the handler ignores (not yet implemented):
        phone, account_ending, routing_number, ssn_last4, bank_name, etc.

    Fixtures required:
        client       – Flask test client (with cookie jar)
        db           – SQLAlchemy session scoped to the test
        user_factory – callable(role=..., password=...) → persisted User
    """

    # ------------------------------------------------------------------
    # 1. Arrange: create a subscriber user
    # ------------------------------------------------------------------
    TEST_PW = "Password123!"
    user = user_factory(role="subscriber", password=TEST_PW)

    # Ensure the password hash is set (some factories skip this)
    if not getattr(user, "password_hash", None):
        user.password_hash = generate_password_hash(TEST_PW)
        db.session.add(user)
        db.session.commit()

    # ------------------------------------------------------------------
    # 2. Log in — do NOT follow_redirects so the session cookie is set
    #    on the very first 302 response, then manually follow once.
    # ------------------------------------------------------------------
    login_url = url_for("auth.login")
    login_resp = client.post(
        login_url,
        data={"email": user.email, "password": TEST_PW},
        follow_redirects=False,
    )
    # Accept redirect (302) or direct success (200)
    assert login_resp.status_code in (
        200,
        302,
    ), f"Login failed with status {login_resp.status_code}"
    if login_resp.status_code == 302:
        # Follow the first redirect to ensure the session cookie is fully established
        client.get(login_resp.headers["Location"])

    # Sanity-check: we should now be authenticated.
    # Any @login_required page should return 200 (not redirect to /auth/login).
    app = client.application
    known_endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    if "main.dashboard" in known_endpoints:
        auth_check = client.get(
            url_for("main.dashboard"), follow_redirects=False
        )
        assert auth_check.status_code != 302 or "/auth/login" not in (
            auth_check.headers.get("Location", "")
        ), (
            "Session appears unauthenticated after login. "
            "Check that login sets the session cookie before the test POSTs."
        )

    # ------------------------------------------------------------------
    # 3. Acquire a fresh CSRF token from an authenticated page
    # ------------------------------------------------------------------
    csrf_token = _get_csrf_token(client)

    # ------------------------------------------------------------------
    # 4. Build the payload using the field names the handler recognises
    #    primary_phone  → user.primary_phone
    #    business_phone → user.business_phone
    #    first_name     → user.first_name  (if column exists)
    #    last_name      → user.last_name   (if column exists)
    # ------------------------------------------------------------------
    EXPECTED_PRIMARY_PHONE = "5551234567"
    EXPECTED_BUSINESS_PHONE = "9015551212"

    payload = {
        "csrf_token": csrf_token,
        # Fields the handler actually writes
        "primary_phone": EXPECTED_PRIMARY_PHONE,
        "business_phone": EXPECTED_BUSINESS_PHONE,
        "first_name": "Smoke",
        "last_name": "Test",
        # Extra fields present in the modal form (handler ignores these, but
        # including them keeps the POST realistic and won't cause errors)
        "subscriber_id": getattr(user, "id", ""),
        "ssn_last4": "1234",
        "phone": "5551234567",  # ignored by handler
        "bank_name": "Test Bank",  # ignored by handler
        "routing_number": "111000025",  # ignored by handler
        "account_ending": "6789",  # ignored by handler
        "business_address": "1 Test Way",
        "ein": "12-3456789",
        "business_city": "Memphis",
        "business_state": "TN",
        "business_zip": "38103",
        "home_address": "123 Home St",
        "same_address_flag": "true",
        "password": "",
    }

    # ------------------------------------------------------------------
    # 5. POST the update
    # ------------------------------------------------------------------
    post_url = url_for("subscriber.update_profile")
    post_resp = client.post(post_url, data=payload, follow_redirects=False)

    assert post_resp.status_code in (200, 302), (
        f"Unexpected status {post_resp.status_code} from update endpoint.\n"
        f"Body: {post_resp.data.decode('utf-8', errors='replace')[:500]}"
    )

    # ------------------------------------------------------------------
    # 6. Verify: reload the user from DB and check persisted fields
    # ------------------------------------------------------------------
    db.session.expire_all()
    db.session.refresh(user)

    # primary_phone must have been written
    actual_primary_phone = getattr(user, "primary_phone", None) or ""
    assert actual_primary_phone.endswith("4567"), (
        f"Expected user.primary_phone to end with '4567' after update, "
        f"got: {actual_primary_phone!r}. "
        f"Confirm the handler is running as the authenticated user and that "
        f"the POST contains key 'primary_phone' (not 'phone')."
    )

    # business_phone must have been written
    actual_business_phone = getattr(user, "business_phone", None) or ""
    assert actual_business_phone.endswith("1212"), (
        f"Expected user.business_phone to end with '1212' after update, "
        f"got: {actual_business_phone!r}."
    )

    # ------------------------------------------------------------------
    # 7. Verify fields the handler does NOT yet write remain untouched
    #    (documents the current stub behaviour; update when the handler
    #     is promoted from stub to full implementation)
    # ------------------------------------------------------------------
    # account_ending is NOT written by the current stub handler
    assert getattr(user, "account_ending", None) != "6789", (
        "account_ending was unexpectedly persisted. "
        "If the handler has been extended to write this field, "
        "remove this assertion and add a positive assertion instead."
    )
