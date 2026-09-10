"""
Module: app/tests/test_oauth_callback.py
Description: Functional test suite for unified OAuth authentication workflows
             (Google, Microsoft, Apple) and Plaid item token exchanges.
"""

from unittest.mock import MagicMock, patch


from app.extensions import db
from app.models import User
from app.models.trace_events import TraceEvent

# ============================================================================
# 1. LOGIN INITIATION TESTS
# ============================================================================


def test_login_initiate_google(client, app):
    """Verify Google OAuth URL generation and state tracking in session."""
    app.config["TESTING"] = True

    response = client.get(
        "/login/google?scope=openid+email&state=fixed-test-state"
    )

    assert response.status_code == 302
    target_url = response.headers.get("Location", "")

    assert "accounts.google.com/o/oauth2/v2/auth" in target_url
    assert "state=fixed-test-state" in target_url
    assert "response_type=code" in target_url
    assert "access_type=offline" in target_url

    with client.session_transaction() as sess:
        assert "oauth_pkce:google" in sess
        assert sess.get("oauth_state:google") == "fixed-test-state"


def test_login_initiate_unknown_provider(client):
    """Verify an unsupported provider returns a 404 response."""
    response = client.get("/login/invalid_provider")
    assert response.status_code == 404


# ============================================================================
# 2. OAUTH CALLBACK TESTS
# ============================================================================


@patch("app.oauth.provider.OAuthProvider.fetch_profile")
@patch("app.oauth.provider.OAuthProvider.exchange_code")
def test_callback_google_success(
    mock_exchange_code, mock_fetch_profile, client, app
):
    """
    Verify full Google OAuth authentication flow using method-level patching.
    Intercepts methods on any OAuthProvider instance created across app contexts.
    """
    mock_exchange_code.return_value = {"access_token": "mock-access-token-123"}
    mock_fetch_profile.return_value = {
        "email": "oauth_subscriber@example.com",
        "name": "Oauth Subscriber",
        "sub": "google-unique-id-999",
    }

    app.config["TESTING"] = True

    # Seed the OAuth state in the session to pass state validation
    test_state = "test-google-state"
    with client.session_transaction() as sess:
        sess["oauth_state:google"] = test_state

    response = client.get(
        f"/callback/google?code=valid-auth-code-xyz&state={test_state}"
    )

    assert response.status_code == 302
    assert "/dashboard" in response.headers.get("Location", "")

    with app.app_context():
        created_user = User.query.filter_by(
            email="oauth_subscriber@example.com"
        ).first()
        assert created_user is not None
        assert created_user.username == "Oauth Subscriber"

        success_event = TraceEvent.query.filter_by(
            user_id=created_user.id, event_type="OAUTH_LOGIN_SUCCESS"
        ).first()
        assert success_event is not None


def test_callback_missing_authorization_code(client, app):
    """Verify callback fails cleanly when authorization code is omitted."""
    app.config["TESTING"] = True
    response = client.get("/callback/google")

    assert response.status_code == 400
    assert response.get_json() == {"error": "missing code"}


@patch("app.services.oauth.verify_ms_token")
@patch("app.oauth.provider.OAuthProvider.fetch_profile")
@patch("app.oauth.provider.OAuthProvider.exchange_code")
def test_callback_microsoft_with_id_token_validation(
    mock_exchange_code, mock_fetch_profile, mock_verify_ms_token, client, app
):
    """Verify Microsoft workflow and ID token validation triggering."""
    mock_exchange_code.return_value = {
        "access_token": "ms-access-777",
        "id_token": "ms-id-jwt-string",
    }
    mock_fetch_profile.return_value = {
        "email": "microsoft_user@example.com",
        "name": "MS User",
        "sub": "ms-sub-id-555",
    }

    mock_verify_ms_token.return_value = {"valid": True}

    app.config["TESTING"] = True

    # Seed the OAuth state in the session to pass state validation
    test_state = "test-ms-state"
    with client.session_transaction() as sess:
        sess["oauth_state:microsoft"] = test_state

    response = client.get(
        f"/callback/microsoft?code=ms-auth-code&state={test_state}"
    )

    assert response.status_code == 302
    mock_verify_ms_token.assert_called_once_with("ms-id-jwt-string")


# ============================================================================
# 3. PLAID CALLBACK TESTS
# ============================================================================


@patch("app.blueprints.plaid_routes._get_plaid_client_and_log_error")
def test_callback_plaid_exchange_success(mock_get_client, client, app):
    """Verify Plaid public token exchange against the POST endpoint using the Plaid SDK."""
    # 1. Ensure test user exists and populate authenticated session
    with app.app_context():
        user = User.query.filter_by(
            email="oauth_subscriber@example.com"
        ).first()
        if not user:
            user = User(
                username="testuser",
                email="oauth_subscriber@example.com",
                password_hash="mock_hash",
            )
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)

        user_id = user.id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    # 2. Mock Plaid Client response
    mock_client = MagicMock()
    mock_client.Item.public_token_exchange.return_value = {
        "access_token": "access-sandbox-de30c6a5-251c-430b-b189-88c",
        "item_id": "item_id_test_string_123",
    }
    mock_get_client.return_value = mock_client

    # 3. Request token exchange
    response = client.post(
        "/exchange_public_token", json={"public_token": "mock-public-999"}
    )

    assert response.status_code == 200
    assert response.get_json()["item_id"] == "item_id_test_string_123"
    mock_client.Item.public_token_exchange.assert_called_once_with(
        "mock-public-999"
    )


def test_callback_plaid_missing_token(client, app):
    """Verify 400 error when exchange endpoint receives payload missing public_token."""
    # 1. Authenticate user session so the request passes auth middleware
    with app.app_context():
        user = User.query.filter_by(email="admin@example.com").first()
        user_id = user.id if user else "00000000-0000-0000-0000-000000000001"

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    # 2. Make request with authenticated session
    response = client.post("/exchange_public_token", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing public token"}
