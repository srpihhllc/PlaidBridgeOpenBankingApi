# =============================================================================
# FILE: app/tests/test_plaid_routes.py
# DESCRIPTION: Test suite covering Plaid Link token generation & exchange flows.
# =============================================================================

from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.models.plaid_item import PlaidItem
from app.models.user import User


@pytest.fixture
def test_user(app):
    """Fixture providing a persisted test user for login session injection."""
    with app.app_context():
        user = User.query.filter_by(email="plaid_tester@example.com").first()
        if not user:
            user = User(
                username="plaid_tester", email="plaid_tester@example.com"
            )
            (
                user.set_password("SecurePass123!")
                if hasattr(user, "set_password")
                else None
            )
            from app.extensions import db

            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
        return user


@pytest.fixture
def authenticated_client(client, test_user):
    """Simulates an authenticated Flask-Login session for current_user."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user.id)
        sess["_fresh"] = True
    return client


# =============================================================================
# 1. LINK TOKEN CREATION TESTS
# =============================================================================


@patch("app.blueprints.plaid_routes._get_plaid_client_and_log_error")
def test_create_link_token_success(mock_get_client, authenticated_client):
    """Verify successful creation and returning of a Plaid Link token."""
    mock_client = MagicMock()
    mock_client.LinkToken.create.return_value = {
        "link_token": "link-sandbox-test-123"
    }
    mock_get_client.return_value = mock_client

    response = authenticated_client.post("/create_link_token")

    assert response.status_code == 200
    assert response.get_json() == {"link_token": "link-sandbox-test-123"}
    mock_client.LinkToken.create.assert_called_once()


@patch("app.blueprints.plaid_routes._get_plaid_client_and_log_error")
def test_create_link_token_sdk_unavailable(
    mock_get_client, authenticated_client
):
    """Verify 503 error returned when Plaid SDK fails to initialize."""
    mock_get_client.return_value = None

    response = authenticated_client.post("/create_link_token")

    assert response.status_code == 503
    assert response.get_json() == {"error": "Service unavailable"}


# =============================================================================
# 2. PUBLIC TOKEN EXCHANGE TESTS
# =============================================================================


@patch("app.blueprints.plaid_routes.ttl_emit")
@patch("app.blueprints.plaid_routes._get_plaid_client_and_log_error")
def test_exchange_public_token_success(
    mock_get_client,
    mock_ttl_emit,
    authenticated_client,
    test_user,
    app,
    monkeypatch,
):
    """Verify token exchange, Fernet encryption, DB persistence, and telemetry."""
    # Ensure encryption key is present in environment
    dummy_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("PLAID_ENCRYPTION_KEY", dummy_key)

    mock_client = MagicMock()
    mock_client.Item.public_token_exchange.return_value = {
        "access_token": "access-sandbox-999-xyz",
        "item_id": "item_id_plaid_123",
    }
    mock_get_client.return_value = mock_client

    response = authenticated_client.post(
        "/exchange_public_token",
        json={"public_token": "public-sandbox-mock-000"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "item_id": "item_id_plaid_123",
    }

    # Assert database insertion and token encryption
    with app.app_context():
        item = PlaidItem.query.filter_by(
            user_id=test_user.id, plaid_item_id="item_id_plaid_123"
        ).first()
        assert item is not None

        # Verify stored access token can be decrypted
        f = Fernet(dummy_key.encode())
        decrypted = f.decrypt(item.plaid_access_token.encode()).decode("utf-8")
        assert decrypted == "access-sandbox-999-xyz"

    # Assert telemetry invocation
    mock_ttl_emit.assert_called_with(
        f"ttl:plaid:success:{test_user.id}", status="success", ttl=300
    )


def test_exchange_public_token_missing_payload(authenticated_client):
    """Verify 400 response when public_token key is omitted in request body."""
    response = authenticated_client.post("/exchange_public_token", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing public token"}


@patch("app.blueprints.plaid_routes._get_plaid_client_and_log_error")
def test_exchange_public_token_sdk_unavailable(
    mock_get_client, authenticated_client
):
    """Verify 503 error returned when SDK client factory yields None."""
    mock_get_client.return_value = None

    response = authenticated_client.post(
        "/exchange_public_token",
        json={"public_token": "public-sandbox-mock-000"},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "Service unavailable"}


@patch("app.blueprints.plaid_routes.ttl_emit")
@patch("app.blueprints.plaid_routes._get_plaid_client_and_log_error")
def test_exchange_public_token_sdk_failure(
    mock_get_client, mock_ttl_emit, authenticated_client, test_user
):
    """Verify failure state handling, error logging, and error telemetry emit."""
    mock_client = MagicMock()
    mock_client.Item.public_token_exchange.side_effect = Exception(
        "Plaid API Timeout"
    )
    mock_get_client.return_value = mock_client

    response = authenticated_client.post(
        "/exchange_public_token",
        json={"public_token": "public-sandbox-mock-000"},
    )

    assert response.status_code == 500
    assert response.get_json() == {"error": "Exchange failed"}

    mock_ttl_emit.assert_called_with(
        f"ttl:plaid:error:{test_user.id}", status="error", ttl=300
    )
