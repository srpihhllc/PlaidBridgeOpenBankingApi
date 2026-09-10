# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_oauth_provider_engine.py

from unittest.mock import patch

import pytest
import responses

from app.oauth.provider import OAuthProvider, ProviderName, _apple_jwks_cache


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    """Ensure a pristine cache state for every independent unit run."""
    _apple_jwks_cache["jwks"] = None
    _apple_jwks_cache["fetched_at"] = 0


@responses.activate
def test_google_exchange_and_profile():
    config = {
        "client_id": "g-id",
        "client_secret": "g-secret",
        "redirect_uri": "g-uri",
    }
    provider = OAuthProvider(ProviderName.GOOGLE, config)

    # 1. Mock Token Exchange
    responses.add(
        responses.POST,
        "https://oauth2.googleapis.com/token",
        json={"access_token": "google-access-token"},
        status=200,
    )
    tokens = provider.exchange_code("code-123")
    assert tokens["access_token"] == "google-access-token"

    # 2. Mock Profile Generation
    responses.add(
        responses.GET,
        "https://openidconnect.googleapis.com/v1/userinfo",
        json={
            "email": "google@test.com",
            "sub": "gsub123",
            "name": "Google User",
        },
        status=200,
    )
    profile = provider.fetch_profile(tokens)
    assert profile["email"] == "google@test.com"


@responses.activate
def test_microsoft_exchange_and_profile():
    config = {
        "client_id": "m-id",
        "client_secret": "m-secret",
        "redirect_uri": "m-uri",
    }
    provider = OAuthProvider(ProviderName.MICROSOFT, config)

    responses.add(
        responses.POST,
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        json={"access_token": "ms-access-token"},
        status=200,
    )
    tokens = provider.exchange_code("code-456")
    assert tokens["access_token"] == "ms-access-token"

    responses.add(
        responses.GET,
        "https://graph.microsoft.com/v1.0/me",
        json={
            "mail": None,
            "userPrincipalName": "ms@test.com",
            "id": "msub456",
            "displayName": "MS User",
        },
        status=200,
    )
    profile = provider.fetch_profile(tokens)
    assert profile["email"] == "ms@test.com"


def test_unsupported_provider_exception():
    provider = OAuthProvider("invalid-provider")
    with pytest.raises(NotImplementedError):
        provider.exchange_code("123")
    with pytest.raises(NotImplementedError):
        provider.fetch_profile({"access_token": "abc"})


@responses.activate
def test_apple_exchange_missing_config():
    provider = OAuthProvider(ProviderName.APPLE, {})
    with pytest.raises(RuntimeError, match="Apple OAuth requires"):
        provider.exchange_code("code")


@responses.activate
@patch("jwt.encode")
def test_apple_exchange_success(mock_jwt_encode):
    mock_jwt_encode.return_value = "mocked.client.assertion.jwt"
    config = {
        "client_id": "app-id",
        "redirect_uri": "app-uri",
        "apple_team_id": "team-id",
        "apple_key_id": "key-id",
        "apple_private_key": "fake-pem-key",
    }
    provider = OAuthProvider(ProviderName.APPLE, config)

    responses.add(
        responses.POST,
        "https://appleid.apple.com/auth/token",
        json={"access_token": "apple-access", "id_token": "apple-id-token"},
        status=200,
    )
    res = provider.exchange_code("apple-code")
    assert res["id_token"] == "apple-id-token"


@responses.activate
@patch("jwt.get_unverified_header")
@patch("jwt.decode")
@patch("jwt.algorithms.RSAAlgorithm.from_jwk")
def test_apple_profile_signature_verification_flow(
    mock_from_jwk, mock_jwt_decode, mock_unverified_header
):
    config = {"client_id": "app-id"}
    provider = OAuthProvider(ProviderName.APPLE, config)

    # Mock JWKS Endpoint Response
    responses.add(
        responses.GET,
        "https://appleid.apple.com/auth/keys",
        json={"keys": [{"kid": "key-123", "kty": "RSA"}]},
        status=200,
    )

    mock_unverified_header.return_value = {"kid": "key-123"}
    mock_from_jwk.return_value = "fake-public-key-object"
    mock_jwt_decode.return_value = {
        "email": "apple@test.com",
        "sub": "asub789",
        "name": "Apple User",
    }

    profile = provider.fetch_profile({"id_token": "valid.mock.jwt"})
    assert profile["email"] == "apple@test.com"


@responses.activate
@patch("jwt.get_unverified_header")
def test_apple_profile_signature_invalid_violates_lockout(
    mock_unverified_header,
):
    import jwt

    config = {"client_id": "app-id"}
    provider = OAuthProvider(ProviderName.APPLE, config)

    responses.add(
        responses.GET,
        "https://appleid.apple.com/auth/keys",
        json={"keys": [{"kid": "key-123"}]},
        status=200,
    )
    mock_unverified_header.return_value = {"kid": "key-123"}

    with patch(
        "jwt.decode",
        side_effect=jwt.PyJWTError("Signature verification failed"),
    ):
        with pytest.raises(
            RuntimeError, match="Invalid Apple ID Token signature"
        ):
            provider.fetch_profile({"id_token": "forged.payload.jwt"})
