# =============================================================================
# FILE: app/tests/test_oauth_combined.py
# DESCRIPTION: Combined smoke tests for Google and Apple OAuth flows using
# the same test harness patterns used elsewhere — meant as a convenience
# to run both providers in a single test case.
# =============================================================================

import base64
import time

import jwt  # PyJWT
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.oauth.provider import OAuthProvider, ProviderName


def _int_to_base64url(n: int) -> str:
    b = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _generate_rsa_jwk_and_pem(kid: str = "test-kid"):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    numbers = pub.public_numbers()
    n_b64 = _int_to_base64url(numbers.n)
    e_b64 = _int_to_base64url(numbers.e)

    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": n_b64,
        "e": e_b64,
    }

    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return private_pem, jwk, kid


def test_google_flow_happy_path(monkeypatch, client, app):
    app.config["TESTING"] = True

    # Simulate token endpoint returning access_token and id_token
    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "access_token": "fake-google-token",
                    "id_token": "fake-id",
                }

        return Resp()

    def mock_get(url, headers=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "email": "test@google.com",
                    "sub": "sub-123",
                    "name": "Google Tester",
                }

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)

    # Seed session state to pass OAuth state validation
    test_state = "test-google-combined-state"
    with client.session_transaction() as sess:
        sess["oauth_state:google"] = test_state

    resp = client.get(
        f"/callback/{ProviderName.GOOGLE.value}?code=abc123&state={test_state}"
    )
    assert resp.status_code in (302, 303)


def test_apple_flow_happy_path(monkeypatch, client, app):
    app.config["TESTING"] = True
    target_client_id = "com.example.app"

    # Set app config and environment variable
    app.config["APPLE_CLIENT_ID"] = target_client_id
    monkeypatch.setenv("APPLE_CLIENT_ID", target_client_id)

    # -------------------------------------------------------------------------
    # THE FIX: Intercept the new instance created by the route and force the
    # target_client_id into self.config where fetch_profile actually reads it.
    # -------------------------------------------------------------------------
    original_init = OAuthProvider.__init__

    def mock_init(self, provider, config=None, *args, **kwargs):
        original_init(self, provider, config, *args, **kwargs)
        if provider == ProviderName.APPLE or provider == "apple":
            if getattr(self, "config", None) is None:
                self.config = {}
            self.config["client_id"] = target_client_id

    monkeypatch.setattr(OAuthProvider, "__init__", mock_init)

    # Generate RSA keypair and sign id_token with target_client_id as audience
    private_pem, jwk, kid = _generate_rsa_jwk_and_pem(kid="test-kid-abc")

    now = int(time.time())
    payload = {
        "iss": "https://appleid.apple.com",
        "aud": target_client_id,
        "exp": now + 300,
        "iat": now,
        "sub": "apple-sub-xyz",
        "email": "test@apple.example",
        "email_verified": "true",
    }
    id_token = jwt.encode(
        payload, private_pem, algorithm="RS256", headers={"kid": kid}
    )
    jwks = {"keys": [jwk]}

    # Patch JWKS fetcher and code exchange
    monkeypatch.setattr("app.oauth.provider._get_apple_jwks", lambda: jwks)

    def mock_exchange(self, code):
        assert code == "abc123"
        return {"id_token": id_token}

    monkeypatch.setattr(OAuthProvider, "exchange_code", mock_exchange)

    # Seed session state to pass OAuth state validation
    test_state = "test-apple-combined-state"
    with client.session_transaction() as sess:
        sess["oauth_state:apple"] = test_state

    resp = client.post(
        f"/callback/{ProviderName.APPLE.value}",
        data={"code": "abc123", "state": test_state},
    )
    assert resp.status_code in (302, 303)
