# Proprietary License
# All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.
# © [Sir Pollards Internal Holistic Healing LLC/Terence Pollard Sr] [2024]

# Code Citations
# This application uses code and libraries from various sources. 
# Please refer to the README.md for detailed information on code usage and attributions.

import os
import requests
import logging
import datetime
import jwt
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from flask_cors import CORS
from functools import wraps
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import csv
import pdfplumber

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_API_KEY')
TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_API_URL')
JWT_SECRET = os.getenv('JWT_SECRET')

# Global variable for account balance
account_balance = 8258.32

# Root endpoint
@app.route('/')
def index():
    return render_template('index.html', account_balance=account_balance)

# Authentication middleware
def authenticate_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except Exception as e:
            logger.error(f"JWT error: {e}")
            return jsonify({'message': 'Token is invalid!'}), 403
        return f(*args, **kwargs)
    return decorated

# Generate JWT token
def generate_jwt_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

# Link bank account
@app.route('/link-bank-account', methods=['POST'])
@authenticate_token
def link_bank_account():
    try:
        data = request.get_json()
        account_number = data.get('account_number')
        routing_number = data.get('routing_number')
        response = requests.post(f"{TREASURY_PRIME_API_URL}/link-account", json={
            'account_number': account_number,
            'routing_number': routing_number
        }, headers={
            'Authorization': f'Bearer {TREASURY_PRIME_API_KEY}',
            'Content-Type': 'application/json'
        })
        if response.status_code == 200:
            return jsonify({'message': 'Bank account linked successfully'}), 200
        else:
            return jsonify({'error': 'Failed to link bank account'}), response.status_code
    except Exception as e:
        logger.error(f"Error in linking bank account: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

# Transfer funds
@app.route('/transfer-funds', methods=['POST'])
@authenticate_token
def transfer_funds():
    try:
        data = request.get_json()
        amount = float(data.get('amount'))
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        result = transfer_funds_to_account(data.get('accessToken'), amount)
        return jsonify(result), 200 if result['success'] else 500
    except Exception as e:
        logger.error(f"Error in transferring funds: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

# Schedule recurring payment
scheduler = BackgroundScheduler()
scheduler.start()

@app.route('/setup-recurring-payment', methods=['POST'])
@authenticate_token
def setup_recurring_payment():
    try:
        data = request.get_json()
        lender_id = data.get('lender_id')
        borrower_id = data.get('borrower_id')
        amount = float(data.get('amount'))
        frequency = data.get('frequency')
        start_date = data.get('start_date')

        if frequency == 'weekly':
            scheduler.add_job(process_scheduled_payment, 'interval', weeks=1, start_date=start_date, args=[lender_id, borrower_id, amount])
        elif frequency == 'biweekly':
            scheduler.add_job(process_scheduled_payment, 'interval', weeks=2, start_date=start_date, args=[lender_id, borrower_id, amount])
        elif frequency == 'monthly':
            scheduler.add_job(process_scheduled_payment, 'interval', weeks=4, start_date=start_date, args=[lender_id, borrower_id, amount])
        else:
            return jsonify({'error': 'Invalid frequency'}), 400

        return jsonify({'message': 'Recurring payment setup successfully'}), 200
    except Exception as e:
        logger.error(f"Error in setting up recurring payment: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

def process_scheduled_payment(lender_id, borrower_id, amount):
    try:
        if verify_lender(lender_id) and verify_borrower(borrower_id):
            if place_transaction(borrower_id, lender_id, amount):
                record_transaction({'lender_id': lender_id, 'borrower_id': borrower_id, 'amount': amount})
                logger.info(f"Scheduled payment processed: {amount} from borrower {borrower_id} to lender {lender_id}")
            else:
                logger.error(f"Failed to process scheduled payment: {amount} from borrower {borrower_id} to lender {lender_id}")
        else:
            logger.error(f"Verification failed for scheduled payment: {amount} from borrower {borrower_id} to lender {lender_id}")
    except Exception as e:
        logger.error(f"Error in processing scheduled payment: {e}")

# Helper functions
def verify_micro_deposits(deposit1, deposit2):
    expected_deposit1 = 0.10
    expected_deposit2 = 0.15
    return deposit1 == expected_deposit1 and deposit2 == expected_deposit2

def transfer_funds_to_account(access_token, amount):
    url = f"{TREASURY_PRIME_API_URL}/transfer-funds"
    headers = {
        'Authorization': f'Bearer {TREASURY_PRIME_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'amount': amount,
        'access_token': access_token
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def record_transaction(transaction_details):
    logger.info(f"Recording transaction: {transaction_details}")

# Download statements
@app.route('/download-statements', methods=['GET'])
@authenticate_token
def download_statements():
    try:
        file_path = 'path/to/your/statements.csv'
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error in downloading statements: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

# PDF Handling Functions
def parse_pdf(file_path):
    statements = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    parts = line.split()
                    if len(parts) >= 3:
                        date = parts[0]
                        description = " ".join(parts[1:-1])
                        amount = parts[-1]
                        # Determine if the amount is a deposit or withdrawal
                        if amount.startswith('-'):
                            transaction_type = 'withdrawal'
                        else:
                            transaction_type = 'deposit'
                        statements.append({
                            'date': date,
                            'description': description,
                            'amount': amount,
                            'transaction_type': transaction_type
                        })
    return statements

@app.route('/upload-pdf', methods=['POST'])
@authenticate_token
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file and file.filename.endswith('.pdf'):
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)
        statements = parse_pdf(file_path)
        save_statements_as_csv(statements, 'statements.csv')
        update_account_balance(statements)
        return jsonify({'message': 'File processed successfully', 'statements': statements}), 200
    return jsonify({'message': 'Invalid file format'}), 400

def save_statements_as_csv(statements, file_path):
    try:
        keys = statements[0].keys()
        with open(file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(statements)
        logger.info(f"Statements saved as '{file_path}'")
    except Exception as e:
        logger.error(f"Error saving CSV file: {e}")

def update_account_balance(statements):
    global account_balance
    for statement in statements:
        amount = float(statement['amount'])
        if statement['transaction_type'] == 'deposit':
            account_balance += amount
        elif statement['transaction_type'] == 'withdrawal':
            account_balance -= amount

if __name__ == '__main__':
    app.run(port=int(os.getenv('PORT', 3000)))




