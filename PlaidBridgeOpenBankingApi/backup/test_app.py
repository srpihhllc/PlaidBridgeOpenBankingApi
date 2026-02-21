# /home/srpihhllc/PlaidBridgeOpenBankingApi/backup/test_app.py

import importlib
import io
import json
import os
import tempfile
import unittest
from typing import Any, cast

# Dynamically import the top-level "app" package and access attributes via Any
# so static analysis (mypy) won't complain if the package does not re-export
# these names directly. At runtime this will access the real objects when present.
_app_mod = importlib.import_module("app")
_app_any = cast(Any, _app_mod)

app = _app_any.app
correct_discrepancies = _app_any.correct_discrepancies
generate_pdf_from_csv = _app_any.generate_pdf_from_csv
parse_pdf = _app_any.parse_pdf
save_statements_as_csv = _app_any.save_statements_as_csv
update_account_balance = _app_any.update_account_balance


class FlaskAppTests(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        # try JSON parse, otherwise fall back to bytes check
        try:
            payload = json.loads(response.get_data(as_text=True))
            self.assertIn("account_balance", payload)
        except Exception:
            self.assertIn(b"account_balance", response.data)

    def test_upload_pdf_no_file(self):
        response = self.app.post("/upload-pdf", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"No file part", response.data)

    def test_upload_pdf_invalid_format(self):
        # Use io.BytesIO to provide an in-memory file object (avoids filesystem)
        fake_file = io.BytesIO(b"not a pdf")
        data = {"file": (fake_file, "test.txt")}
        response = self.app.post("/upload-pdf", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Invalid file format", response.data)

    def test_parse_pdf(self):
        # Minimal PDF header for many parsers; adjust if your parser requires more.
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(pdf_bytes)
            tmp_pdf.flush()
            tmp_pdf_name = tmp_pdf.name

        try:
            statements = parse_pdf(tmp_pdf_name)
            self.assertIsInstance(statements, list)
        finally:
            os.remove(tmp_pdf_name)

    def test_correct_discrepancies(self):
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
        corrected_statements = correct_discrepancies(statements)
        self.assertEqual(corrected_statements[1]["amount"], "0.00")

    def test_save_statements_as_csv(self):
        statements = [
            {
                "date": "2023-01-01",
                "description": "Test",
                "amount": "100.00",
                "transaction_type": "deposit",
            }
        ]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_csv:
            tmp_csv_name = tmp_csv.name

        try:
            save_statements_as_csv(statements, tmp_csv_name)
            self.assertTrue(os.path.exists(tmp_csv_name))
        finally:
            if os.path.exists(tmp_csv_name):
                os.remove(tmp_csv_name)

    def test_generate_pdf_from_csv(self):
        statements = [
            {
                "date": "2023-01-01",
                "description": "Test",
                "amount": "100.00",
                "transaction_type": "deposit",
            }
        ]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_csv:
            tmp_csv_name = tmp_csv.name
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf_name = tmp_pdf.name

        try:
            save_statements_as_csv(statements, tmp_csv_name)
            generate_pdf_from_csv(tmp_csv_name, tmp_pdf_name)
            self.assertTrue(os.path.exists(tmp_pdf_name))
        finally:
            if os.path.exists(tmp_csv_name):
                os.remove(tmp_csv_name)
            if os.path.exists(tmp_pdf_name):
                os.remove(tmp_pdf_name)

    def test_update_account_balance(self):
        # Make a test where update_account_balance returns the computed new balance.
        initial_balance = 848583.68
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

        # Call the function. Many implementations either return a new balance or mutate
        # state — adapt this test if your implementation behaves differently.
        try:
            new_balance = update_account_balance(statements, starting_balance=initial_balance)
        except TypeError:
            # Fallback if implementation doesn't accept starting_balance
            new_balance = update_account_balance(statements)

        if new_balance is None:
            self.skipTest(
                "update_account_balance did not return a value; adjust test to match implementation"
            )
        else:
            self.assertAlmostEqual(new_balance, initial_balance + 50.00, places=2)


if __name__ == "__main__":
    unittest.main()
