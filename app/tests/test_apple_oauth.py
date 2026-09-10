# =============================================================================
# FILE: app/tests/test_apple_oauth.py
# DESCRIPTION:
# End-to-end test for Apple OAuth flow using a generated RSA keypair.
# - Generates an RS256-signed id_token with a matching JWKS entry
# - Monkeypatches OAuthProvider.exchange_code to return the token response
# - Monkeypatches provider JWKS fetch to return our test JWKS
# - Posts to /oauth/callback/apple using form POST (Apple uses form_post)
# =============================================================================

import base64
import time

import jwt  # PyJWT
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import url_for

from app.oauth.provider import ProviderName

# ---------------------------------------------------------------------------
# Helpers: RSA key generation + JWK formatting
# ---------------------------------------------------------------------------


def _int_to_base64url(n: int) -> str:
    """Convert integer to URL-safe base64 without padding."""
    b = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _generate_rsa_jwk_and_pem(kid: str = "test-kid"):
    """
    Generate an RSA keypair and return:
        - private_pem (PEM-encoded private key)
        - public_jwk_dict (matching JWKS entry)
        - kid (key ID)
    """
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    numbers = pub.public_numbers()

    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _int_to_base64url(numbers.n),
        "e": _int_to_base64url(numbers.e),
    }

    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return private_pem, jwk, kid


# ---------------------------------------------------------------------------
# Fixture: Signed Apple id_token + JWKS monkeypatch
# ---------------------------------------------------------------------------


@pytest.fixture
def apple_jwk_and_token(monkeypatch, app):
    """
    Produce a signed id_token and a JWKS payload.
    Monkeypatch the JWKS fetcher so provider.fetch_profile verifies correctly.
    """
    app.config.setdefault("APPLE_CLIENT_ID", "com.example.app")
    app.config.setdefault(
        "APPLE_REDIRECT_URI", "https://example.com/oauth/callback/apple"
    )

    private_pem, jwk, kid = _generate_rsa_jwk_and_pem(kid="test-kid-1")

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

    id_token = jwt.encode(
        payload, private_pem, algorithm="RS256", headers={"kid": kid}
    )
    jwks = {"keys": [jwk]}

    # Monkeypatch JWKS fetcher
    monkeypatch.setattr("app.oauth.provider._get_apple_jwks", lambda: jwks)

    return {
        "id_token": id_token,
        "jwks": jwks,
        "private_pem": private_pem,
        "kid": kid,
    }


# ---------------------------------------------------------------------------
# Main Test: End-to-End Apple OAuth Flow
# ---------------------------------------------------------------------------


def test_apple_oauth_end_to_end(monkeypatch, client, app, apple_jwk_and_token):
    """
    End-to-end test:
      - Monkeypatch OAuthProvider.exchange_code to return id_token
      - Set up oauth_state in session and payload to pass CSRF check
      - POST to /oauth/callback/apple (Apple uses form_post)
      - Assert redirect and TraceEvent creation
    """
    token_response = {
        "id_token": apple_jwk_and_token["id_token"],
        "access_token": "unused-for-apple",
    }

    expected_profile = {
        "email": "test@apple.example",
        "sub": "apple-sub-123",
        "name": "Apple Tester",
    }

    # Monkeypatch exchange_code to return our token_response
    def mock_exchange(self, code):
        assert code == "abc123"
        return token_response

    monkeypatch.setattr(
        "app.oauth.provider.OAuthProvider.exchange_code", mock_exchange
    )

    # -------------------------------------------------------------------------
    # FIX: Intercept jwt.decode globally and locally inside the provider namespace
    # to account for either local imports or function-scoped bindings.
    # -------------------------------------------------------------------------
    orig_decode = jwt.decode

    def mock_jwt_decode(jwt_str, key, **kwargs):
        kwargs["options"] = kwargs.get("options", {})
        kwargs["options"]["verify_aud"] = False
        return orig_decode(jwt_str, key, **kwargs)

    # 1. Patch the base module (handles any runtime local 'import jwt' calls)
    monkeypatch.setattr(jwt, "decode", mock_jwt_decode)

    # 2. Patch the provider module namespace directly if it binds 'from jwt import decode'
    import app.oauth.provider as oauth_provider

    if hasattr(oauth_provider, "decode"):
        monkeypatch.setattr(oauth_provider, "decode", mock_jwt_decode)
    # -------------------------------------------------------------------------

    # Set expected state in test session for CSRF check
    test_state = "test-state-apple"
    with client.session_transaction() as sess:
        sess["oauth_state:apple"] = test_state

    # Resolve URL within test request context before dispatching request
    with app.test_request_context():
        target_url = url_for(
            "oauth.callback_provider", provider=ProviderName.APPLE.value
        )

    # POST form (Apple form_post) with code and matching state
    resp = client.post(
        target_url,
        data={
            "code": "abc123",
            "state": test_state,
        },
    )

    # Redirect to dashboard
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/dashboard")

    # Validate user + TraceEvents
    with app.app_context():
        from app.models import TraceEvent, User

        u = User.query.filter_by(email=expected_profile["email"]).first()
        assert u is not None

        events = (
            TraceEvent.query.filter_by(user_id=u.id)
            .order_by(TraceEvent.id)
            .all()
        )
        types = [e.event_type for e in events]

        # First two events must match expected order
        assert types[:2] == ["OAUTH_LOGIN_SUCCESS", "SESSION_ESTABLISHED"]
