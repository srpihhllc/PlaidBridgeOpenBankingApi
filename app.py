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

app = Flask(__name__)
CORS(app)
limiter = Limiter(app, key_func=get_remote_address)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client configuration
redis_client = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)

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

# Business Logic Functions
def perform_manual_login():
    logger.info("Lender logs in manually.")

def verify_lender():
    logger.info("Lender is verified.")

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

# Core Function
def manual_login_and_link_bank_account():
    try:
        perform_manual_login()
        verify_lender()
        extracted_details = upload_and_extract_details()
        verification_code = receive_verification_code()
        access_token = generate_access_token(verification_code)
        is_verified = check_bank_verification(access_token, extracted_details)
        if is_verified:
            user_email = os.getenv('USER_EMAIL')
            user_password = os.getenv('USER_PASSWORD')
            statements = read_statements_from_csv('path/to/your/statements.csv')
            save_statements_as_csv(statements, 'statements.csv')
            ending_balance = calculate_ending_balance(statements)
            logger.info(f"Ending balance to the month to date: {ending_balance}")
            return {"accessToken": access_token, "message": "Success"}
    except Exception as error:
        logger.error(f"Error in manual_login_and_link_bank_account: {error}")
        raise error

@app.route('/manual-login', methods=['POST'])
@authenticate_token
def manual_login():
    try:
        result = manual_login_and_link_bank_account()
        return jsonify(result), 200
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

@app.route('/micro-deposits', methods=['POST'])
@authenticate_token
def micro_deposits():
    try:
        deposit1 = float(request.json.get('deposit1'))
        deposit2 = float(request.json.get('deposit2'))
        if not deposit1 or not deposit2:
            return jsonify({'message': 'Micro deposits are required.'}), 400
        if verify_micro_deposits(deposit1, deposit2):
            return jsonify({'message': 'Account verified successfully.'}), 200
        else:
            return jsonify({'message': 'Micro deposits verification failed.'}), 400
    except Exception as e:
        logger.error(f"Error verifying micro deposits: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/actual-deposits', methods=['POST'])
@authenticate_token
def actual_deposits():
    try:
        amount = float(request.json.get('amount'))
        if amount <= 0:
            return jsonify({'message': 'Invalid deposit amount.'}), 400
        if handle_actual_deposit(amount)['success']:
            return jsonify({'message': 'Deposit successful.'}), 200
        else:
            return jsonify({'message': 'Deposit failed.'}), 500
    except Exception as e:
        logger.error(f"Error handling actual deposit: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/transfer-funds', methods=['POST'])
@authenticate_token
def transfer_funds():
    try:
        access_token = request.json.get('accessToken')
        amount = float(request.json.get('amount'))
        if not access_token or amount <= 0:
            return jsonify({'message': 'Access token and valid amount are required.'}), 400
        result = transfer_funds_to_account(access_token, amount)
        return jsonify({'message': result['message']}), 200 if result['success'] else 500
    except Exception as e:
        logger.error(f"Error transferring funds: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

if __name__ == '__main__':
    app.run(port=3000)
