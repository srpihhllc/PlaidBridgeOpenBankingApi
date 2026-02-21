# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_subscriber_update.py

import re

from flask import url_for
from werkzeug.security import generate_password_hash


def _extract_csrf(response_data: bytes) -> str | None:
    """Extract CSRF token value from HTML response bytes using a simple regex."""
    try:
        html = response_data.decode("utf-8")
    except Exception:
        html = str(response_data)
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


def test_subscriber_update_smoke(client, db, user_factory):
    """
    Smoke test: create a subscriber, sign in, fetch a page to get CSRF token,
    POST an update to subscriber.update_profile, and assert DB persisted change.

    Fixtures expected:
    - client: Flask test client
    - db: SQLAlchemy session (scoped) for tests
    - user_factory: factory to create User instances; must accept keyword args
      for role and password (or return a User with an accessible email/password).
    """

    # Arrange: create a subscriber user with known password
    TEST_PW = "Password123!"
    # user_factory should return a persisted user; adapt if your factory signature differs
    user = user_factory(role="subscriber", password=TEST_PW)

    # If the factory doesn't set password_hash, try to set it here and commit
    if getattr(user, "password_hash", None) is None:
        user.password_hash = generate_password_hash(TEST_PW)
        db.session.add(user)
        db.session.commit()

    # Act: log in through the web flow (keeps session semantics identical to real app)
    login_url = url_for("auth.login")
    resp = client.post(
        login_url,
        data={"email": user.email, "password": TEST_PW},
        follow_redirects=True,
    )
    assert resp.status_code in (200, 302)

    # Fetch the dashboard (or a page that contains the modal form) to acquire CSRF token
    # Use a canonical page that renders the modal (auth.me or subscriber dashboard)
    # Try subscriber dashboard endpoint names that might exist; fallback to "/"
    possible_pages = [
        (
            url_for("auth.me_dashboard")
            if "auth.me_dashboard" in {r.endpoint for r in client.application.url_map.iter_rules()}
            else None
        ),
        (
            url_for("main.dashboard")
            if "main.dashboard" in {r.endpoint for r in client.application.url_map.iter_rules()}
            else None
        ),
        "/",
    ]
    page_html = None
    for p in possible_pages:
        if not p:
            continue
        r = client.get(p)
        if r.status_code == 200 and b"csrf_token" in r.data:
            page_html = r.data
            break
    if page_html is None:
        # final attempt: load the register_subscriber view or any auth page
        r = client.get(url_for("auth.register_subscriber"))
        page_html = r.data

    csrf_token = _extract_csrf(page_html) or ""
    assert csrf_token, (
        "Could not extract CSRF token from page; ensure CSRF is enabled and form "
        "renders a hidden token."
    )

    # Prepare update payload; name keys must match your modal form and handler expectations
    payload = {
        "subscriber_id": getattr(user, "id", None),
        "ssn_last4": "1234",
        "phone": "5551234567",
        "bank_name": "Test Bank",
        "routing_number": "111000025",
        "account_ending": "6789",
        "business_address": "1 Test Way",
        "ein": "12-3456789",
        "business_city": "Memphis",
        "business_state": "TN",
        "business_zipcode": "38103",
        "business_phone": "9015551212",
        "home_address": "123 Home St",
        "same_address_flag": "true",
        "password": "",  # leave empty when not changing password
        "csrf_token": csrf_token,
    }

    # Post to the canonical endpoint; use url_for to remain independent of hard-coded path
    post_url = url_for("subscriber.update_profile")
    post_resp = client.post(post_url, data=payload, follow_redirects=False)

    # Assert: we expect either a redirect (302) back to dashboard or 200
    assert post_resp.status_code in (
        200,
        302,
    ), f"Unexpected status from update endpoint: {post_resp.status_code}"

    # Refresh from DB and assert the profile/user fields were updated
    # Handler may persist fields on user or profile; check both (adapt names to your models)
    db.session.expire_all()
    # Try to detect profile relation
    profile = getattr(user, "profile", None)
    if profile is None:
        # If no profile relation, assume fields were written to user model
        db.session.refresh(user)
        assert (
            getattr(user, "primary_phone", "")
            or getattr(user, "phone", "")
            or getattr(user, "phone_number", "")
        ).endswith("4567") or getattr(user, "account_ending", "") == "6789"
    else:
        db.session.refresh(profile)
        assert profile.primary_phone.endswith("4567") or str(profile.account_ending).endswith(
            "6789"
        )
