# =============================================================================
# FILE: app/tests/test_oauth_combined.py
# DESCRIPTION: Combined smoke tests for Google and Apple OAuth flows using
# the same test harness patterns used elsewhere — meant as a convenience
# to run both providers in a single test case.
# =============================================================================

import time
import json
import base64

import jwt  # PyJWT
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from flask import url_for

from app.oauth.provider import ProviderName


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
    # Simulate token endpoint returning access_token and id_token
    def mock_post(url, data=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "fake-google-token", "id_token": "fake-id"}

        return Resp()

    def mock_get(url, headers=None, timeout=10):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"email": "test@google.com", "sub": "sub-123", "name": "Google Tester"}

        return Resp()

    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)

    resp = client.get(f"/oauth/callback/{ProviderName.GOOGLE.value}?code=abc123")
    assert resp.status_code in (302, 303)


def test_apple_flow_happy_path(monkeypatch, client, app):
    # Generate RSA keypair and build id_token
    app.config.setdefault("APPLE_CLIENT_ID", "com.example.app")
    private_pem, jwk, kid = _generate_rsa_jwk_and_pem(kid="test-kid-abc")

    now = int(time.time())
    payload = {
        "iss": "https://appleid.apple.com",
        "aud": app.config["APPLE_CLIENT_ID"],
        "exp": now + 300,
        "iat": now,
        "sub": "apple-sub-xyz",
        "email": "test@apple.example",
        "email_verified": "true",
    }
    id_token = jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})
    jwks = {"keys": [jwk]}

    # Monkeypatch JWKS fetcher and OAuthProvider.exchange_code to return id_token
    monkeypatch.setattr("app.oauth.provider._get_apple_jwks", lambda: jwks)

    def mock_exchange(self, code):
        assert code == "abc123"
        return {"id_token": id_token}

    monkeypatch.setattr("app.oauth.provider.OAuthProvider.exchange_code", mock_exchange)

    resp = client.post(f"/oauth/callback/{ProviderName.APPLE.value}", data={"code": "abc123"})
    assert resp.status_code in (302, 303)