from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import logging
import redis
import csv
import os
import jwt
from functools import wraps
import requests
from dotenv import load_dotenv
from limits.storage import RedisStorage
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Redis client configuration
redis_url = os.getenv('REDIS_URL')
redis_client = redis.from_url(redis_url)

# Configure Flask-Limiter to use Redis
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url
)
limiter.init_app(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Root Endpoint
@app.route('/')
def index():
    return "Welcome to the Flask Banking API!"

# Environment Variables
MOCK_USERNAME = os.getenv('MOCK_USERNAME', 'srpollardsihhllc@gmail.com')
MOCK_PASSWORD = os.getenv('MOCK_PASSWORD', 'your_2Late2little$')
USER_EMAIL = os.getenv('USER_EMAIL', 'your_srpollardsihhllc@gmail.com')
USER_PASSWORD = os.getenv('USER_PASSWORD', 'your_skeeMdralloP1$t')
JWT_SECRET = os.getenv('JWT_SECRET', 'your_wiwmU1jZdt+uWOsmoaywjCVXgxaAZbBuOY7HqQt2ydY=')
TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_API_KEY')
TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_API_URL')

# Authentication Middleware
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

# Generate JWT Token
def generate_jwt_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

# Refresh JWT Token
@app.route('/refresh-token', methods=['POST'])
@authenticate_token
def refresh_token():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_token = generate_jwt_token(user_id)
        return jsonify({'jwtToken': new_token}), 200
    except Exception as e:
        logger.error(f"Error in refreshing token: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

# Business Logic Functions
def perform_manual_login(username, password):
    logger.info("Lender logs in manually.")
    if username == MOCK_USERNAME and password == MOCK_PASSWORD:
        return True
    return False

def verify_lender(lender_id):
    # Implement lender verification logic
    logger.info("Lender is verified.")
    return True

def verify_borrower(borrower_id):
    # Implement borrower verification logic
    logger.info("Borrower is verified.")
    return True

def upload_and_extract_details():
    logger.info("Uploading and extracting details from voided check for account verification.")
    return {'accountNumber': '7030 3429 9651', 'routingNumber': '026 015 053'}

def check_bank_verification(access_token, extracted_details):
    logger.info("Lender must complete bank verification before access token is released.")
    bank_verified = True
    if bank_verified:
        logger.info("Bank verification successful. Access token generated and shared with lender.")
        return True
    else:
        logger.info("Bank verification failed. Access token will not be released.")
        return False

def manual_login_and_link_bank_account(username, password):
    try:
        if not perform_manual_login(username, password):
            return {'error': 'Invalid credentials'}
        verify_lender(username)
        extracted_details = upload_and_extract_details()
        verification_code = '123456'  # Mock verification code
        access_token = generate_jwt_token(username)
        jwt_token = generate_jwt_token(username)
        is_verified = check_bank_verification(access_token, extracted_details)
        if is_verified:
            statements = read_statements_from_csv('path/to/your/statements.csv')
            save_statements_as_csv(statements, 'statements.csv')
            ending_balance = calculate_ending_balance(statements)
            logger.info(f"Ending balance to the month to date: {ending_balance}")
            # Refresh JWT token after linking
            new_jwt_token = generate_jwt_token(username)
            return {"accessToken": access_token, "jwtToken": new_jwt_token, "message": "Success"}
    except Exception as error:
        logger.error(f"Error in manual_login_and_link_bank_account: {error}")
        raise error

@app.route('/manual-login', methods=['POST'])
@authenticate_token
def manual_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        result = manual_login_and_link_bank_account(username, password)
        return jsonify(result), 200 if 'error' not in result else 403
    except Exception as e:
        logger.error(f"Error in manual login and bank account linking: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

# CSV Handling Functions
def read_statements_from_csv(file_path):
    statements = []
    try:
        with open(file_path, mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                statements.append(row)
        return statements
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return []

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

def calculate_ending_balance(statements):
    return sum(float(statement['amount']) for statement in statements)

# Helper Functions
def verify_micro_deposits(deposit1, deposit2):
    expected_deposit1 = 0.10
    expected_deposit2 = 0.15
    return deposit1 == expected_deposit1 and deposit2 == expected_deposit2

def handle_actual_deposit(amount):
    return {'success': True}

def transfer_funds_to_account(access_token, amount):
    logger.info(f"Transferring {amount} to the actual account using access token {access_token}")
    return {'success': True, 'message': 'Funds transferred successfully'}

def integrate_open_banking_api(api_url, payload):
    response = requests.post(api_url, json=payload)
    return response.json()

# Treasury Prime Integration Functions
def get_treasury_prime_account_details(account_id):
    url = f"{TREASURY_PRIME_API_URL}/accounts/{account_id}"
    headers = {
        'Authorization': f'Bearer {TREASURY_PRIME_API_KEY}',
        'Content-Type': 'application/json',
    }
    response = requests.get(url, headers=headers)
    return response.json()

def create_treasury_prime_account(account_data):
    url = f"{TREASURY_PRIME_API_URL}/accounts"
    headers = {
        'Authorization': f'Bearer {TREASURY_PRIME_API_KEY}',
        'Content-Type': 'application/json',
    }
    response = requests.post(url, headers=headers, json=account_data)
    return response.json()

# Recurring Payments
scheduler = BackgroundScheduler()
scheduler.start()

@app.route('/setup-recurring-payment', methods=['POST'])
@authenticate_token
def setup_recurring_payment():
    try:
        data = request.get_json()
        lender_id = data.get('lender_id')
        borrower_id = data.get('borrower_id')
        amount = data.get('amount')
        frequency = data.get('frequency')  # 'weekly' or 'monthly'
        start_date = data.get('start_date')  # e.g., '2023-10-01'

        # Schedule the recurring payment
        if frequency == 'weekly':
            scheduler.add_job(process_recurring_payment, 'interval', weeks=1, start_date=start_date, args=[lender_id, borrower_id, amount])
        elif frequency == 'monthly':
            scheduler.add_job(process_recurring_payment, 'interval', weeks=4, start_date=start_date, args=[lender_id, borrower_id, amount])
        else:
            return jsonify({'error': 'Invalid frequency'}), 400

        return jsonify({'message': 'Recurring payment setup successfully'}), 200
    except Exception as e:
        logger.error(f"Error in setting up recurring payment: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

def process_recurring_payment(lender_id, borrower_id, amount):
    try:
        # Verify lender and borrower
        if verify_lender(lender_id) and verify_borrower(borrower_id):
            # Place the transaction into the original account
            if place_transaction(lender_id, borrower_id, amount):
                record_transaction({'lender_id': lender_id, 'borrower_id': borrower_id, 'amount': amount})
                logger.info(f"Recurring payment processed: {amount} from borrower {borrower_id} to lender {lender_id}")
            else:
                logger.error(f"Failed to place recurring payment: {amount} from borrower {borrower_id} to lender {lender_id}")
        else:
            logger.error(f"Verification failed for recurring payment: {amount} from borrower {borrower_id} to lender {lender_id}")
    except Exception as e:
        logger.error(f"Error in processing recurring payment: {e}")

@app.route('/complete-transaction', methods=['POST'])
@authenticate_token
def complete_transaction():
    try:
        data = request.get_json()
        lender_id = data.get('lender_id')
        borrower_id = data.get('borrower_id')
        amount = data.get('amount')
        # Verify lender and borrower
        if verify_lender(lender_id) and verify_borrower(borrower_id):
            # Place the transaction into the original account
            if place_transaction(lender_id, borrower_id, amount):
                record_transaction({'lender_id': lender_id, 'borrower_id': borrower_id, 'amount': amount})
                return jsonify({'message': 'Transaction completed successfully'}), 200
            else:
                return jsonify({'error': 'Transaction placement failed'}), 403
        else:
            return jsonify({'error': 'Verification failed'}), 403
    except Exception as e:
        logger.error(f"Error in completing transaction: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

def place_transaction(lender_id, borrower_id, amount):
    # Implement logic to place the transaction into the original account
    logger.info(f"Placing transaction from lender {lender_id} to borrower {borrower_id} with amount {amount}")
    return True

def record_transaction(transaction_details):
    # Record the transaction details
    logger.info(f"Transaction recorded: {transaction_details}")
    # Save to database or file

@app.route('/repay-loan', methods=['POST'])
@authenticate_token
def repay_loan():
    try:
        data = request.get_json()
        borrower_id = data.get('borrower_id')
        amount = data.get('amount')
        # Process loan repayment
        if process_loan_repayment(borrower_id, amount):
            return jsonify({'message': 'Loan repayment successful'}), 200
        else:
            return jsonify({'error': 'Loan repayment failed'}), 403
    except Exception as e:
        logger.error(f"Error in loan repayment: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

def process_loan_repayment(borrower_id, amount):
    # Implement loan repayment logic
    logger.info(f"Loan repayment processed for borrower {borrower_id} with amount {amount}")
    return True

if __name__ == '__main__':
    app.run(debug=True)

# Code Citations
# Include any code citations or references here.
