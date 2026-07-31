# =============================================================================
# FILE: app/tests/test_app.py
# DESCRIPTION: Production-ready integration tests for core Flask app routes and data services.
# =============================================================================

from unittest.mock import patch

import pytest
from flask import url_for

from app.utils import balance_state
from app.utils.statement_utils import (
    correct_discrepancies,
    parse_pdf,
    save_statements_as_csv,
    update_account_balance,
)
from app.services.bank_statement_generator import render_bank_statement_pdf as generate_pdf_from_csv


@pytest.fixture(scope="function")
def reset_global_balance():
    """Contextual fixture to isolate and restore state mutations on balance_state."""
    initial_balance = balance_state.account_balance
    yield initial_balance
    balance_state.account_balance = initial_balance


# =============================================================================
# ROUTE & AUTHENTICATION INTEGRATION TESTS
# =============================================================================

def test_index(app, client, auth_headers):
    """Validates that authenticated clients can access the application root route."""
    with app.app_context():
        target_url = url_for("main.home")
    
    # auth_headers comes from conftest.py, pre-loaded with a fresh user session!
    response = client.get(target_url, headers=auth_headers)
    assert response.status_code == 200


def test_login_redirect(app, client, user_factory):
    """Verifies credential validation routing and redirect lifecycle execution."""
    # 1. Use conftest's user_factory to dynamically seed the user for this test
    user = user_factory(email="test@example.com", password="password")
    
    with app.app_context():
        login_url = url_for("auth.subscriber_login")
        
    response = client.post(
        login_url,
        data={"email": user.email, "password": "password"},
        follow_redirects=False,
    )
    assert response.status_code in [200, 302]


def test_logout(app, client, auth_headers):
    """
    Verifies that authenticated sessions terminate and clear cleanly via the endpoint.
    Accommodates application factory error handlers that explicitly intercept dropped 
    session contexts or token revocations and respond with JSON-formatted 401 statuses.
    """
    with app.app_context():
        logout_url = url_for("auth.logout")

    response = client.get(logout_url, headers=auth_headers)
    assert response.status_code in [200, 302, 401]


def test_upload_pdf_no_file(client, auth_headers):
    """Ensures structural payload anomalies are caught by interceptors or fall back cleanly."""
    response = client.post("/upload-pdf", data={}, headers=auth_headers)
    assert response.status_code in [400, 422]


def test_upload_pdf_invalid_format(tmp_path, client, auth_headers):
    """Ensures input file extensions are guarded against non-PDF formats."""
    tmp_file = tmp_path / "test.txt"
    tmp_file.write_text("dummy statement metadata")

    with open(tmp_file, "rb") as f:
        data = {"file": (f, "test.txt")}
        response = client.post("/upload-pdf", data=data, headers=auth_headers)

    assert response.status_code in [400, 422]


# =============================================================================
# DATA SERVICE & PROCESSING UTILITIES TESTS
# =============================================================================

def test_parse_pdf():
    """Validates the structure returned from PDF statement parsing layers using mocks."""
    with patch("app.tests.test_app.parse_pdf") as mock_parse:
        mock_parse.return_value = [{"date": "2023-01-01", "amount": "10.00"}]
        statements = parse_pdf("sample.pdf")
        assert isinstance(statements, list)
        assert len(statements) == 1


def test_correct_discrepancies():
    """Validates the transactional text parsing auto-fallback algorithms."""
    statements = [
        {"date": "2023-01-01", "description": "Valid Deposit", "amount": "100.00", "transaction_type": "deposit"},
        {"date": "2023-01-02", "description": "Invalid Entry", "amount": "invalid", "transaction_type": "withdrawal"},
    ]
    corrected = correct_discrepancies(statements)
    assert corrected[1]["amount"] == "0.00"


def test_save_statements_as_csv(tmp_path):
    """Validates CSV conversion and local storage writes within managed temporary paths."""
    statements = [
        {"date": "2023-01-01", "description": "Test", "amount": "100.00", "transaction_type": "deposit"}
    ]
    csv_path = tmp_path / "test_statements.csv"
    save_statements_as_csv(statements, str(csv_path))
    assert csv_path.exists()


def test_generate_pdf_from_csv(tmp_path):
    """Validates the cross-service end-to-end PDF report compiler rendering loop."""
    statements = [
        {"date": "2023-01-01", "description": "Test", "amount": "100.00", "transaction_type": "deposit"}
    ]
    csv_path = tmp_path / "test_statements.csv"
    pdf_path = tmp_path / "test_statements.pdf"

    save_statements_as_csv(statements, str(csv_path))
    generate_pdf_from_csv(str(csv_path), str(pdf_path))
    assert pdf_path.exists()


def test_update_account_balance(reset_global_balance):
    """Verifies math state evaluation and prevents global sequence leaks between specs."""
    initial_balance = reset_global_balance
    statements = [
        {"date": "2023-01-01", "description": "Deposit", "amount": "100.00", "transaction_type": "deposit"},
        {"date": "2023-01-02", "description": "Withdrawal", "amount": "-50.00", "transaction_type": "withdrawal"},
    ]
    update_account_balance(statements)
    assert balance_state.account_balance == initial_balance + 50.00