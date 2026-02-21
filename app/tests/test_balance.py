# =============================================================================
# FILE: app/tests/test_app.py
# DESCRIPTION: Integration tests for core Flask app routes and PDF/CSV services.
# =============================================================================

import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.user import User
from app.services.bank_statement_generator import render_bank_statement_pdf as generate_pdf_from_csv

# ✅ Import the module, not the float
from app.utils import balance_state

# ✅ Import helpers from statement_utils
from app.utils.statement_utils import (
    correct_discrepancies,
    parse_pdf,
    save_statements_as_csv,
    update_account_balance,
)


@pytest.fixture
def app():
    app_obj = create_app(env_name="testing")
    app_obj.testing = True

    with app_obj.app_context():
        db.drop_all()
        db.create_all()

        test_user = User(
            email="test@example.com",
            username="testuser",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(test_user)
        db.session.commit()

    return app_obj


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def _login():
        return client.post(
            "/login",
            data={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

    return _login


def test_index(client, login):
    login()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome to PlaidBridge" in response.data


def test_login(client, login):
    response = login()
    assert response.status_code == 302


def test_logout(client, login):
    login()
    response = client.get("/logout")
    assert response.status_code == 302


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert body["data"]["status"] == "ok"


def test_upload_pdf_no_file(client):
    response = client.post("/upload-pdf", data={})
    assert response.status_code == 400
    assert b"No file part" in response.data


def test_upload_pdf_invalid_format(client):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tmp:
        tmp.write("dummy text")
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            data = {"file": (f, "test.txt")}
            response = client.post("/upload-pdf", data=data)
    finally:
        os.remove(tmp_path)

    assert response.status_code == 400
    assert b"Invalid file format" in response.data


def test_parse_pdf():
    statements = parse_pdf("sample.pdf")
    assert isinstance(statements, list)


def test_correct_discrepancies():
    statements = [
        {
            "date": "2023-01-01",
            "description": "Test",
            "amount": "100.00",
            "transaction_type": "deposit",
        },
        {
            "date": "2023-01-02",
            "description": "Test",
            "amount": "invalid",
            "transaction_type": "withdrawal",
        },
    ]
    corrected = correct_discrepancies(statements)
    assert corrected[1]["amount"] == "0.00"


def test_save_statements_as_csv():
    statements = [
        {
            "date": "2023-01-01",
            "description": "Test",
            "amount": "100.00",
            "transaction_type": "deposit",
        }
    ]
    path = "test_statements.csv"
    try:
        save_statements_as_csv(statements, path)
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_generate_pdf_from_csv():
    statements = [
        {
            "date": "2023-01-01",
            "description": "Test",
            "amount": "100.00",
            "transaction_type": "deposit",
        }
    ]
    csv_path = "test_statements.csv"
    pdf_path = "test_statements.pdf"

    try:
        save_statements_as_csv(statements, csv_path)
        generate_pdf_from_csv(csv_path, pdf_path)
        assert os.path.exists(pdf_path)
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def test_update_account_balance():
    initial_balance = balance_state.account_balance
    statements = [
        {
            "date": "2023-01-01",
            "description": "Test",
            "amount": "100.00",
            "transaction_type": "deposit",
        },
        {
            "date": "2023-01-02",
            "description": "Test",
            "amount": "-50.00",
            "transaction_type": "withdrawal",
        },
    ]
    update_account_balance(statements)
    assert balance_state.account_balance == initial_balance + 50.00
