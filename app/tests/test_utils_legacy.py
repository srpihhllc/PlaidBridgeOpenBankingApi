#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_utils_legacy.py

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.utils_legacy import (
    analyze_loan_agreement,
    create_bank_statement,
    detect_fraudulent_transaction,
    execute_smart_contract,
    get_pythonanywhere_cpu_quota,
    merge_pdfs,
    notify_authorities,
    time_since,
)


# ----------------------------------------------------------------------
# PythonAnywhere API
# ----------------------------------------------------------------------


def test_get_pythonanywhere_cpu_quota_success(monkeypatch):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"daily_cpu_limit": 100}

    request = MagicMock(return_value=response)
    monkeypatch.setattr("app.utils_legacy.requests.get", request)
    monkeypatch.setenv("API_TOKEN", "test-token")

    result = get_pythonanywhere_cpu_quota()

    assert result == {"daily_cpu_limit": 100}

    request.assert_called_once_with(
        "https://www.pythonanywhere.com/api/v0/user/srpihhllc/cpu/",
        headers={"Authorization": "Token test-token"},
        timeout=10,
    )


def test_get_pythonanywhere_cpu_quota_without_token(monkeypatch):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"status": "ok"}

    request = MagicMock(return_value=response)
    monkeypatch.setattr("app.utils_legacy.requests.get", request)
    monkeypatch.delenv("API_TOKEN", raising=False)

    result = get_pythonanywhere_cpu_quota()

    assert result == {"status": "ok"}

    request.assert_called_once_with(
        "https://www.pythonanywhere.com/api/v0/user/srpihhllc/cpu/",
        headers={},
        timeout=10,
    )


def test_get_pythonanywhere_cpu_quota_failure(monkeypatch):
    response = MagicMock()
    response.status_code = 429
    response.content = b"rate limited"

    monkeypatch.setattr(
        "app.utils_legacy.requests.get",
        MagicMock(return_value=response),
    )

    result = get_pythonanywhere_cpu_quota()

    assert result == {
        "error": "Unexpected status 429",
        "details": "rate limited",
    }


# ----------------------------------------------------------------------
# Loan and Fraud Utilities
# ----------------------------------------------------------------------


def test_analyze_loan_agreement_approves_clean_text():
    result = analyze_loan_agreement("This agreement has standard terms.")

    assert result == {"status": "approved"}


@pytest.mark.parametrize(
    "term",
    [
        "hidden fees",
        "predatory interest rates",
        "undisclosed penalties",
    ],
)
def test_analyze_loan_agreement_flags_unethical_terms(term):
    result = analyze_loan_agreement(f"The contract contains {term}.")

    assert result == {
        "status": "flagged",
        "reason": f"Contains unethical term: {term}",
    }


def test_detect_fraudulent_transaction_flags_large_amount():
    assert detect_fraudulent_transaction("Normal purchase", 5000.01) is True


@pytest.mark.parametrize(
    "description",
    [
        "unexpected large withdrawal",
        "account drained",
        "unauthorized payment",
    ],
)
def test_detect_fraudulent_transaction_flags_suspicious_description(
    description,
):
    assert detect_fraudulent_transaction(description, 25.00) is True


def test_detect_fraudulent_transaction_allows_normal_transaction():
    assert detect_fraudulent_transaction("Grocery store purchase", 75.00) is False


def test_notify_authorities(capsys):
    result = notify_authorities("Suspicious transaction detected")

    assert result == {"status": "notified"}
    assert "Fraud Alert: Suspicious transaction detected" in capsys.readouterr().out


# ----------------------------------------------------------------------
# Smart Contract Utility
# ----------------------------------------------------------------------


def test_execute_smart_contract_executes_active_agreement(monkeypatch):
    agreement = MagicMock()
    agreement.status = "active"

    session = MagicMock()
    session.get.return_value = agreement

    monkeypatch.setattr("app.extensions.db.session", session)

    from app.models.loan_agreement import LoanAgreement

    result = execute_smart_contract(42)

    assert result == {
        "contract_status": "executed",
        "loan_agreement_id": 42,
    }
    assert agreement.status == "under_contract"
    session.get.assert_called_once_with(LoanAgreement, 42)
    session.commit.assert_called_once_with()


@pytest.mark.parametrize("status", ["pending", "completed", "cancelled"])
def test_execute_smart_contract_rejects_non_active_agreement(
    monkeypatch,
    status,
):
    agreement = MagicMock()
    agreement.status = status

    session = MagicMock()
    session.get.return_value = agreement

    monkeypatch.setattr("app.extensions.db.session", session)

    result = execute_smart_contract(42)

    assert result == {
        "contract_status": "failed",
        "reason": "Invalid agreement or status.",
    }
    session.commit.assert_not_called()


def test_execute_smart_contract_rejects_missing_agreement(monkeypatch):
    session = MagicMock()
    session.get.return_value = None

    monkeypatch.setattr("app.extensions.db.session", session)

    result = execute_smart_contract(999)

    assert result == {
        "contract_status": "failed",
        "reason": "Invalid agreement or status.",
    }
    session.commit.assert_not_called()


# ----------------------------------------------------------------------
# Time Utility
# ----------------------------------------------------------------------


def test_time_since_returns_seconds():
    dt = datetime.now(timezone.utc) - timedelta(seconds=30)

    assert time_since(dt) == "30s"


def test_time_since_returns_minutes():
    dt = datetime.now(timezone.utc) - timedelta(minutes=3)

    assert time_since(dt) == "3m"


def test_time_since_returns_hours():
    dt = datetime.now(timezone.utc) - timedelta(hours=2)

    assert time_since(dt) == "2h"


def test_time_since_returns_days():
    dt = datetime.now(timezone.utc) - timedelta(days=4)

    assert time_since(dt) == "4d"


# ----------------------------------------------------------------------
# PDF Generation
# ----------------------------------------------------------------------


def test_create_bank_statement_returns_pdf():
    data = {
        "name": "Jane Doe",
        "account_number": "123456789",
        "balance": 1250.50,
        "transactions": [
            {
                "date": "2026-09-29",
                "description": "Deposit",
                "amount": 500.00,
            }
        ],
    }

    result = create_bank_statement(data)

    assert isinstance(result, BytesIO)
    assert result.tell() == 0
    assert result.read(4) == b"%PDF"


def test_create_bank_statement_with_missing_values():
    result = create_bank_statement({})

    assert isinstance(result, BytesIO)
    assert result.read(4) == b"%PDF"


def test_create_bank_statement_with_invalid_signature_continues():
    result = create_bank_statement(
        {"name": "Jane Doe"},
        signature_base64="not-valid-base64",
    )

    assert isinstance(result, BytesIO)
    assert result.read(4) == b"%PDF"


# ----------------------------------------------------------------------
# PDF Merging
# ----------------------------------------------------------------------


def test_merge_pdfs_from_bytes():
    first_pdf = create_bank_statement({"name": "First"})
    second_pdf = create_bank_statement({"name": "Second"})

    result = merge_pdfs([first_pdf, second_pdf])

    assert isinstance(result, BytesIO)
    assert result.tell() == 0
    assert result.read(4) == b"%PDF"


def test_merge_pdfs_from_file_paths(tmp_path: Path):
    first_pdf = create_bank_statement({"name": "First"})
    second_pdf = create_bank_statement({"name": "Second"})

    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"

    first_path.write_bytes(first_pdf.getvalue())
    second_path.write_bytes(second_pdf.getvalue())

    result = merge_pdfs([first_path, str(second_path)])

    assert isinstance(result, BytesIO)
    assert result.tell() == 0
    assert result.read(4) == b"%PDF"