import unittest
import os
import json
from app import app, account_balance

class FlaskTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'PlaidBridgeOpenBankingAPI', response.data)

    def test_upload_pdf_no_file(self):
        response = self.app.post('/upload-pdf', data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'No file part', response.data)

    def test_upload_pdf_invalid_format(self):
        data = {
            'file': (open('test.txt', 'rb'), 'test.txt')
        }
        response = self.app.post('/upload-pdf', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Invalid file format', response.data)

    def test_create_link_token(self):
        response = self.app.get('/create-link-token')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'link_token', response.data)

    def test_exchange_public_token_no_token(self):
        response = self.app.post('/exchange-public-token', data=json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Public token is required', response.data)

    def test_verify_account_no_id(self):
        response = self.app.post('/verify-account', data=json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Account ID is required', response.data)

if __name__ == '__main__':
    unittest.main()
