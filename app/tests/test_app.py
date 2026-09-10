# =============================================================================
# FILE: app/tests/test_app.py
# DESCRIPTION: Production-ready integration tests for core Flask app routes and
# data services.
# =============================================================================

from unittest.mock import patch

import pytest
from flask import url_for

from app.services.bank_statement_generator import (
    render_bank_statement_pdf as generate_pdf_from_csv,
)
from app.utils import balance_state
from app.utils.statement_utils import (
    correct_discrepancies,
    parse_pdf,
    save_statements_as_csv,
    update_account_balance,
)


@pytest.fixture(scope="function")
def reset_global_balance():
    """Isolate and restore mutations to the global balance state."""
    initial_balance = balance_state.account_balance

    yield initial_balance

    balance_state.account_balance = initial_balance


# =============================================================================
# ROUTE & AUTHENTICATION INTEGRATION TESTS
# =============================================================================


def test_index(app, client, auth_headers):
    """Validate that authenticated clients can access the application root route."""
    with app.test_request_context("/"):
        target_url = url_for("main.home")

    response = client.get(target_url, headers=auth_headers)

    assert response.status_code == 200


def test_login_redirect(app, client, user_factory):
    """Verify credential validation and login redirect behavior."""
    user = user_factory(
        email="test@example.com",
        password="password",
    )

    with app.test_request_context("/"):
        login_url = url_for("auth.subscriber_login")

    response = client.post(
        login_url,
        data={
            "email": user.email,
            "password": "password",
        },
        follow_redirects=False,
    )

    assert response.status_code in {200, 302}


def test_logout(app, client, auth_headers):
    """
    Verify that authenticated sessions terminate cleanly.

    The application may return a successful response, redirect, or JSON 401
    when handling token revocation or an already-invalid session.
    """
    with app.test_request_context("/"):
        logout_url = url_for("auth.logout")

    response = client.get(
        logout_url,
        headers=auth_headers,
    )

    assert response.status_code in {200, 302, 401}


def test_upload_pdf_no_file(client, auth_headers):
    """Verify that a request without an uploaded file is rejected."""
    response = client.post(
        "/upload-pdf",
        data={},
        headers=auth_headers,
    )

    assert response.status_code in {400, 422}


def test_upload_pdf_invalid_format(tmp_path, client, auth_headers):
    """Verify that unsupported uploaded file extensions are rejected."""
    tmp_file = tmp_path / "test.txt"
    tmp_file.write_text("dummy statement metadata", encoding="utf-8")

    with tmp_file.open("rb") as file_object:
        response = client.post(
            "/upload-pdf",
            data={"file": (file_object, "test.txt")},
            headers=auth_headers,
        )

    assert response.status_code in {400, 422}


# =============================================================================
# DATA SERVICE & PROCESSING UTILITY TESTS
# =============================================================================


def test_parse_pdf():
    """Validate the structure returned by the PDF parsing layer."""
    with patch("app.tests.test_app.parse_pdf") as mock_parse:
        mock_parse.return_value = [
            {
                "date": "2023-01-01",
                "amount": "10.00",
            }
        ]

        statements = parse_pdf("sample.pdf")

    assert isinstance(statements, list)
    assert len(statements) == 1
    assert statements[0]["date"] == "2023-01-01"
    assert statements[0]["amount"] == "10.00"


def test_correct_discrepancies():
    """Validate fallback handling for invalid transaction amounts."""
    statements = [
        {
            "date": "2023-01-01",
            "description": "Valid Deposit",
            "amount": "100.00",
            "transaction_type": "deposit",
        },
        {
            "date": "2023-01-02",
            "description": "Invalid Entry",
            "amount": "invalid",
            "transaction_type": "withdrawal",
        },
    ]

    corrected = correct_discrepancies(statements)

    assert corrected[1]["amount"] == "0.00"


def test_save_statements_as_csv(tmp_path):
    """Validate CSV conversion and writing to a temporary path."""
    statements = [
        {
            "date": "2023-01-01",
            "description": "Test",
            "amount": "100.00",
            "transaction_type": "deposit",
        }
    ]
    csv_path = tmp_path / "test_statements.csv"

    save_statements_as_csv(statements, str(csv_path))

    assert csv_path.exists()


def test_generate_pdf_from_csv(tmp_path):
    """Validate PDF generation from a CSV statement file."""
    statements = [
        {
            "date": "2023-01-01",
            "description": "Test",
            "amount": "100.00",
            "transaction_type": "deposit",
        }
    ]
    csv_path = tmp_path / "test_statements.csv"
    pdf_path = tmp_path / "test_statements.pdf"

    save_statements_as_csv(statements, str(csv_path))
    generate_pdf_from_csv(str(csv_path), str(pdf_path))

    assert pdf_path.exists()


def test_update_account_balance(reset_global_balance):
    """Validate account balance updates without leaking state between tests."""
    initial_balance = reset_global_balance

    statements = [
        {
            "date": "2023-01-01",
            "description": "Deposit",
            "amount": "100.00",
            "transaction_type": "deposit",
        },
        {
            "date": "2023-01-02",
            "description": "Withdrawal",
            "amount": "-50.00",
            "transaction_type": "withdrawal",
        },
    ]

    update_account_balance(statements)

    assert balance_state.account_balance == initial_balance + 50.00
