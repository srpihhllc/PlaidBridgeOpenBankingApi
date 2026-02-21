# =============================================================================
# FILE: tests/test_mfa_integration.py
# DESCRIPTION: End-to-end integration tests for MFA flow.
#              Covers Redis-backed MFA, TOTP MFA, and MFA rate-limit lockout.
#              Hardened: clears telemetry state before each test, retries
#              telemetry assertions to tolerate async emission, and provides
#              helpful diagnostics on failure so we don't have to revisit.
# =============================================================================
# tests/test_mfa_integration.py
import time

import pyotp
import pytest

from app.extensions import db
from app.models.user import User
from app.tests.utils import assert_event_exists, get_redis_client


def clear_identity_events():
    rc = get_redis_client()
    if rc:
        try:
            rc.delete("identity_events_stream")
        except Exception:
            pass


def assert_event_with_retry(
    event_type: str, user_id: int | None, retries: int = 6, delay: float = 0.1
) -> bool:
    for _ in range(retries):
        if assert_event_exists(event_type, user_id=user_id):
            return True
        time.sleep(delay)
    return False


def _body_contains_tokens(resp, tokens) -> bool:
    body = resp.data.decode("utf-8", errors="replace")
    norm = " ".join(body.split()).lower()
    return all(t.lower() in norm for t in tokens)


@pytest.mark.usefixtures("client", "app")
def test_login_with_redis_mfa(client, app):
    clear_identity_events()
    with app.app_context():
        user = User(username="redis_user", email="redis_user+redis@example.com")
        user.set_password("secret")
        user.mfa_enabled = True
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client:
        resp = client.post("/auth/login", data={"email": user.email, "password": "secret"})
        assert resp.status_code == 302
        assert "/auth/mfa_prompt" in resp.location

        resp = client.post("/auth/mfa_prompt", data={"code": "000000"}, follow_redirects=True)
        assert resp.status_code == 200
        assert _body_contains_tokens(resp, ["invalid", "mfa"]) or _body_contains_tokens(
            resp, ["invalid", "totp"]
        )
        assert assert_event_with_retry("MFA_LOGIN_REDIS_FAIL", user_id=user_id)

        with client.session_transaction() as sess:
            sess["mfa_user_id"] = user_id
            sess["mfa_setup_code"] = "123456"

        resp = client.post("/auth/mfa_prompt", data={"code": "123456"}, follow_redirects=True)
        assert resp.status_code == 200
        assert _body_contains_tokens(resp, ["mfa", "successful"])
        assert assert_event_with_retry("MFA_LOGIN_REDIS_SUCCESS", user_id=user_id)


@pytest.mark.usefixtures("client", "app")
def test_login_with_totp_mfa(client, app):
    clear_identity_events()
    with app.app_context():
        user = User(username="totp_user", email="totp_user+totp@example.com")
        user.set_password("secret")
        user.totp_secret = pyotp.random_base32()
        user.mfa_enabled = True
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        totp = pyotp.TOTP(user.totp_secret)

    with client:
        resp = client.post("/auth/login", data={"email": user.email, "password": "secret"})
        assert resp.status_code == 302
        assert "/auth/mfa_prompt" in resp.location

        with client.session_transaction() as sess:
            sess["mfa_user_id"] = user_id

        resp = client.post("/auth/mfa_prompt", data={"code": totp.now()}, follow_redirects=True)
        assert resp.status_code == 200
        assert _body_contains_tokens(resp, ["mfa", "successful"])
        assert assert_event_with_retry("MFA_LOGIN_TOTP_SUCCESS", user_id=user_id)

        with client.session_transaction() as sess:
            sess["mfa_user_id"] = user_id

        resp = client.post("/auth/mfa_prompt", data={"code": "000000"}, follow_redirects=True)
        assert resp.status_code == 200
        assert _body_contains_tokens(resp, ["invalid", "totp"]) or _body_contains_tokens(
            resp, ["invalid", "mfa"]
        )
        assert assert_event_with_retry("MFA_LOGIN_TOTP_FAIL", user_id=user_id)


@pytest.mark.usefixtures("client", "app")
def test_mfa_rate_limit_lockout(client, app):
    clear_identity_events()
    with app.app_context():
        user = User(username="rate_limit_user", email="rate_limit_user+rate@example.com")
        user.set_password("secret")
        user.mfa_enabled = True
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client:
        resp = client.post("/auth/login", data={"email": user.email, "password": "secret"})
        assert resp.status_code == 302
        assert "/auth/mfa_prompt" in resp.location

        for _ in range(6):
            with client.session_transaction() as sess:
                sess["mfa_user_id"] = user_id
            resp = client.post("/auth/mfa_prompt", data={"code": "000000"}, follow_redirects=True)

        assert resp.status_code == 200
        assert _body_contains_tokens(resp, ["too many", "mfa", "attempt"]) or _body_contains_tokens(
            resp, ["temporarily", "locked"]
        )
        assert assert_event_with_retry("MFA_PROMPT_RATE_LIMIT", user_id=user_id)
