#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_treasury_routes.py

from unittest.mock import patch

import pytest

from app import create_app

TREASURY_PREFIX = "/api/v1/treasury"


@pytest.fixture
def app():
    app = create_app("testing")
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@patch("app.routes.treasury_routes.suspend_card", return_value=True)
def test_suspend_card_success(mock_suspend, client):
    response = client.post(f"{TREASURY_PREFIX}/cards/card-123/suspend")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "message": "Card card-123 suspended.",
    }
    mock_suspend.assert_called_once_with("card-123")


@patch("app.routes.treasury_routes.suspend_card", return_value=False)
def test_suspend_card_failure(mock_suspend, client):
    response = client.post(f"{TREASURY_PREFIX}/cards/card-123/suspend")

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "Failed to suspend card card-123.",
    }
    mock_suspend.assert_called_once_with("card-123")


@patch(
    "app.routes.treasury_routes.suspend_card",
    side_effect=RuntimeError("card service unavailable"),
)
def test_suspend_card_exception(mock_suspend, client):
    response = client.post(f"{TREASURY_PREFIX}/cards/card-123/suspend")

    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error",
        "message": "card service unavailable",
    }
    mock_suspend.assert_called_once_with("card-123")


@patch("app.routes.treasury_routes.unfreeze_card", return_value=True)
def test_unfreeze_card_success(mock_unfreeze, client):
    response = client.post(f"{TREASURY_PREFIX}/cards/card-123/unfreeze")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "message": "Card card-123 unfrozen.",
    }
    mock_unfreeze.assert_called_once_with("card-123")


@patch("app.routes.treasury_routes.unfreeze_card", return_value=False)
def test_unfreeze_card_failure(mock_unfreeze, client):
    response = client.post(f"{TREASURY_PREFIX}/cards/card-123/unfreeze")

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "Failed to unfreeze card card-123.",
    }
    mock_unfreeze.assert_called_once_with("card-123")


@patch(
    "app.routes.treasury_routes.unfreeze_card",
    side_effect=RuntimeError("card service unavailable"),
)
def test_unfreeze_card_exception(mock_unfreeze, client):
    response = client.post(f"{TREASURY_PREFIX}/cards/card-123/unfreeze")

    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error",
        "message": "card service unavailable",
    }
    mock_unfreeze.assert_called_once_with("card-123")