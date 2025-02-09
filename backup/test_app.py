import unittest
import os
import json
from app import app, parse_pdf, correct_discrepancies, save_statements_as_csv, generate_pdf_from_csv, update_account_balance

class FlaskAppTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'account_balance', response.data)

    def test_upload_pdf_no_file(self):
        response = self.app.post('/upload-pdf', data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'No file part', response.data)

    def test_upload_pdf_invalid_format(self):
        data = {
            'file': (open('test.txt', 'rb'), 'test.txt')
        }
        response = self.app.post('/upload-pdf', data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Invalid file format', response.data)

    def test_parse_pdf(self):
        # Assuming you have a sample PDF file for testing
        statements = parse_pdf('sample.pdf')
        self.assertIsInstance(statements, list)

    def test_correct_discrepancies(self):
        statements = [
            {'date': '2023-01-01', 'description': 'Test', 'amount': '100.00', 'transaction_type': 'deposit'},
            {'date': '2023-01-02', 'description': 'Test', 'amount': 'invalid', 'transaction_type': 'withdrawal'}
        ]
        corrected_statements = correct_discrepancies(statements)
        self.assertEqual(corrected_statements[1]['amount'], '0.00')

    def test_save_statements_as_csv(self):
        statements = [
            {'date': '2023-01-01', 'description': 'Test', 'amount': '100.00', 'transaction_type': 'deposit'}
        ]
        save_statements_as_csv(statements, 'test_statements.csv')
        self.assertTrue(os.path.exists('test_statements.csv'))
        os.remove('test_statements.csv')

    def test_generate_pdf_from_csv(self):
        statements = [
            {'date': '2023-01-01', 'description': 'Test', 'amount': '100.00', 'transaction_type': 'deposit'}
        ]
        save_statements_as_csv(statements, 'test_statements.csv')
        generate_pdf_from_csv('test_statements.csv', 'test_statements.pdf')
        self.assertTrue(os.path.exists('test_statements.pdf'))
        os.remove('test_statements.csv')
        os.remove('test_statements.pdf')

    def test_update_account_balance(self):
        initial_balance = 848583.68
        statements = [
            {'date': '2023-01-01', 'description': 'Test', 'amount': '100.00', 'transaction_type': 'deposit'},
            {'date': '2023-01-02', 'description': 'Test', 'amount': '-50.00', 'transaction_type': 'withdrawal'}
        ]
        update_account_balance(statements)
        self.assertEqual(account_balance, initial_balance + 50.00)

if __name__ == '__main__':
    unittest.main()
