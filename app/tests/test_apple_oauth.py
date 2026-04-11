# =============================================================================
# FILE: app/tests/test_apple_oauth.py
# DESCRIPTION: End-to-end test for Apple OAuth flow using a generated RSA keypair.
# - Generates an RS256-signed id_token with a matching JWKS entry
# - Monkeypatches OAuthProvider.exchange_code to return the token response
# - Monkeypatches provider JWKS fetch to return our test JWKS
# - Posts to /oauth/callback/apple using form POST (Apple uses form_post)
# =============================================================================

import base64
import json
import time

import pytest
import jwt  # PyJWT
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from flask import url_for

from app.oauth.provider import _get_apple_jwks as real_get_apple_jwks
from app.oauth.provider import OAuthProvider, ProviderName


def _int_to_base64url(n: int) -> str:
    b = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _generate_rsa_jwk_and_pem(kid: str = "test-kid"):
    """
    Generate an RSA keypair, return (private_pem, public_jwk_dict, kid).
    The public_jwk_dict matches the format returned by JWKS endpoints.
    """
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


@pytest.fixture
def apple_jwk_and_token(monkeypatch, app):
    """
    Produce a signed id_token and a JWKS payload; monkeypatch the JWKS fetcher
    used by the provider so provider.fetch_profile will find the matching public key.
    """
    # Ensure APPLE_CLIENT_ID is present so JWT audience check passes when provider verifies.
    app.config.setdefault("APPLE_CLIENT_ID", "com.example.app")
    app.config.setdefault("APPLE_REDIRECT_URI", "https://example.com/oauth/callback/apple")

    private_pem, jwk, kid = _generate_rsa_jwk_and_pem(kid="test-kid-1")

    # Build id_token payload
    now = int(time.time())
    payload = {
        "iss": "https://appleid.apple.com",
        "aud": app.config["APPLE_CLIENT_ID"],
        "exp": now + 300,
        "iat": now,
        "sub": "apple-sub-123",
        "email": "test@apple.example",
        "email_verified": "true",
    }

    id_token = jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})

    jwks = {"keys": [jwk]}

    # Monkeypatch the JWKS fetcher used by the provider to return our jwks
    monkeypatch.setattr("app.oauth.provider._get_apple_jwks", lambda: jwks)

    return {"id_token": id_token, "jwks": jwks, "private_pem": private_pem, "kid": kid}


def test_apple_oauth_end_to_end(monkeypatch, client, app, apple_jwk_and_token):
    """
    End-to-end test:
      - Monkeypatch OAuthProvider.exchange_code to return a response containing id_token
      - Call the callback endpoint via POST form (Apple form_post)
      - Assert redirect and that user and TraceEvent rows were created as expected
    """
    token_response = {"id_token": apple_jwk_and_token["id_token"], "access_token": "unused-for-apple"}
    profile_response = {"email": "test@apple.example", "sub": "apple-sub-123", "name": "Apple Tester"}

    # Monkeypatch OAuthProvider.exchange_code to return our token_response
    def mock_exchange(self, code):
        assert code == "abc123"
        return token_response

    # Let provider.fetch_profile run normally (it will verify id_token using the monkeypatched JWKS)
    monkeypatch.setattr("app.oauth.provider.OAuthProvider.exchange_code", mock_exchange)

    # Call the unified callback as a form POST (Apple form_post)
    resp = client.post(
        url_for("oauth.callback_provider", provider=ProviderName.APPLE.value),
        data={"code": "abc123"},
    )

    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/dashboard")

    # Verify user and TraceEvents were created
    with app.app_context():
        from app.models import User, TraceEvent

        u = User.query.filter_by(email=profile_response["email"]).first()
        # Our provider.fetch_profile decodes id_token and returns email; _create_or_get_user will create the user
        assert u is not None

        # Two ordered trace events should exist for this user
        events = TraceEvent.query.filter_by(user_id=u.id).order_by(TraceEvent.id).all()
        types = [e.event_type for e in events]
        assert types[:2] == ["OAUTH_LOGIN_SUCCESS", "SESSION_ESTABLISHED"]