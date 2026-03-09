import pytest

# =============================================================================
# FILE: app/tests/api/test_transactions_endpoint.py
# DESCRIPTION: Unit tests for /api/v1/core/transactions endpoint.
#              Clean, deterministic, aligned with global auth fixtures.
# =============================================================================


@pytest.fixture
def fresh_auth_headers(app):
    """Fixture to provide fresh JWT auth headers for testing."""
    from flask_jwt_extended import create_access_token

    from app.extensions import db  # Import here to avoid module-level import issues
    from app.models.user import User  # Import here to avoid module-level import issues

    with app.app_context():
        # Ensure a test user exists (ID 1)
        user = User.query.get(1)
        if not user:
            user = User(
                id=1,
                email="test@example.com",
                username="testuser",
                password_hash="fake_hash",  # Not used for JWT
            )
            db.session.add(user)
            db.session.commit()

        # Convert to string to fix InvalidSubjectError
        token = create_access_token(identity=str(user.id))
        return {"Authorization": f"Bearer {token}"}


# =============================================================================
# TEST 1 — JSON REQUIRED
# =============================================================================


def test_api_transactions_json_required(client, fresh_auth_headers):
    """
    POST without JSON should return 422 with an explicit error message.
    JSON validation must occur before JWT validation.
    """
    resp = client.post(
        "/api/v1/core/transactions",
        data="not-json",
        headers=fresh_auth_headers,  # Now uses the defined fixture with a valid user
    )

    assert resp.status_code == 422
    assert b"Request must be JSON" in resp.data


# =============================================================================
# TEST 2 — SUCCESSFUL QUEUEING
# =============================================================================


def test_api_transactions_queueing_success(client, fresh_auth_headers):
    """
    POST with valid JSON should succeed and return a mock transaction_id.
    """
    payload = {"amount": 100, "description": "X", "account_id": "A"}

    resp = client.post(
        "/api/v1/core/transactions",
        json=payload,
        headers=fresh_auth_headers,
    )

    assert resp.status_code == 200
    body = resp.get_json()

    # Envelope
    assert body["status"] == "success"

    # Data payload
    data = body.get("data", {})
    assert "transaction_id" in data
    assert data["transaction_id"].startswith("MOCK_")


# =============================================================================
# TEST 3 — AUTH SMOKE TEST (ISOLATES JWT LAYER)
# =============================================================================


def test_api_transactions_auth_only_smoke_test(client, fresh_auth_headers):
    """
    Minimal smoke test to confirm that JWT verification succeeds.
    Ensures the route does not return 401 when authentication is valid.
    """
    resp = client.post(
        "/api/v1/core/transactions",
        json={},  # Missing required fields should trigger 422, not 401
        headers=fresh_auth_headers,
    )

    # If JWT is valid, we should never get 401 here.
    assert resp.status_code != 401, (
        "Unexpected 401 — JWT verification failed. "
        f"Response body: {resp.data.decode(errors='ignore')}"
    )

    # Expected outcome: missing required fields -> 422
    assert resp.status_code == 422