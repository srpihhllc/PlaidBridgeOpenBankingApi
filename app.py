import os
import requests
import logging
import datetime
import jwt
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from functools import wraps
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import csv
import pdfplumber
import tkinter as tk
from tkinter import ttk

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

# Root endpoint
@app.route('/')
def index():
    return "Welcome to PlaidBridgeOpenBankingApi!"

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

# Receive micro deposits
@app.route('/receive-micro-deposits', methods=['POST'])
@authenticate_token
def receive_micro_deposits():
    try:
        data = request.get_json()
        deposit1 = float(data.get('deposit1'))
        deposit2 = float(data.get('deposit2'))
        if verify_micro_deposits(deposit1, deposit2):
            return jsonify({'message': 'Micro deposits verified successfully'}), 200
        else:
            return jsonify({'error': 'Micro deposits verification failed'}), 403
    except Exception as e:
        logger.error(f"Error in receiving micro deposits: {e}")
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
    account_balance_label.config(text=f"Account Balance: ${account_balance:,.2f}")

# Tkinter Interface Setup
root = tk.Tk()
root.title("PlaidBridgeOpenBankingApi Interface")

# Set up frames for different sections
quick_actions_frame = ttk.Frame(root)
banking_frame = ttk.Frame(root)
wallets_frame = ttk.Frame(root)

# Quick Actions Frame Content
quick_actions_label = ttk.Label(quick_actions_frame, text="QUICK ACTIONS")
banking_button = ttk.Button(quick_actions_frame, text="Banking")
cards_button = ttk.Button(quick_actions_frame, text="Cards")
transfers_button = ttk.Button(quick_actions_frame, text="Transfers")

# Banking Frame Content
account_balance_label = ttk.Label(banking_frame, text=f"Account Balance: ${account_balance:,.2f}")
account_number_label = ttk.Label(banking_frame, text="Account Number: *** *** *** 9651")
add_money_button = ttk.Button(banking_frame, text="Add money")
move_money_button = ttk.Button(banking_frame, text="Move money")

# Wallets Frame Content
primary_wallet_label = ttk.Label(wallets_frame, text="Primary\n$8,258.32")
business_wallet_label = ttk.Label(wallets_frame, text="Business\n$0.00")

# API endpoint URLs (change these to match your actual endpoints)
BASE_URL = "http://localhost:3000"
LINK_BANK_ACCOUNT_URL = f"{BASE_URL}/link-bank-account"
RECEIVE_MICRO_DEPOSITS_URL = f"{BASE_URL}/receive-micro-deposits"
TRANSFER_FUNDS_URL = f"{BASE_URL}/transfer-funds"
SETUP_RECURRING_PAYMENT_URL = f"{BASE_URL}/setup-recurring-payment"
DOWNLOAD_STATEMENTS_URL = f"{BASE_URL}/download-statements"

def link_bank_account():
    data = {
        "account_number": "123456789",
        "routing_number": "987654321"
    }
    response = requests.post(LINK_BANK_ACCOUNT_URL, json=data)
    if response.status_code == 200:
        print("Bank account linked successfully")
    else:
        print("Failed to link bank account")

def receive_micro_deposits():
    data = {
        "deposit1": 0.10,
        "deposit2": 0.15
    }
    response = requests.post(RECEIVE_MICRO_DEPOSITS_URL, json=data)
    if response.status_code == 200:
        print("Micro deposits verified successfully")
    else:
        print("Failed to verify micro deposits")

def transfer_funds():
    data = {
        "amount": 1000.00,
        "accessToken": "your_access_token"
    }
    response = requests.post(TRANSFER_FUNDS_URL, json=data)
    if response.status_code == 200:
        print("Funds transferred successfully")
    else:
        print("Failed to transfer funds")

def setup_recurring_payment():
    data = {
        "lender_id": "lender123",
        "borrower_id": "borrower456",
        "amount": 500.00,
        "frequency": "weekly",
        "start_date": "2023-10-01"
    }
    response = requests.post(SETUP_RECURRING_PAYMENT_URL, json=data)
    if response.status_code == 200:
        print("Recurring payment setup successfully")
    else:
        print("Failed to setup recurring payment")

def download_statements():
    response = requests.get(DOWNLOAD_STATEMENTS_URL)
    if response.status_code == 200:
        with open("statements.csv", "wb") as f:
            f.write(response.content)
        print("Statements downloaded successfully")
    else:
        print("Failed to download statements")

# Bind buttons to functions
add_money_button.config(command=link_bank_account)
move_money_button.config(command=transfer_funds)

# Layout all frames and widgets using grid or pack method (grid used here for example)
quick_actions_frame.grid(row=0, column=0, padx=10, pady=10)
quick_actions_label.grid(row=0, column=0, padx=5, pady=5)
banking_button.grid(row=1, column=0, padx=5, pady=5)
cards_button.grid(row=2, column=0, padx=5, pady=5)
transfers_button.grid(row=3, column=0, padx=5, pady=5)

banking_frame.grid(row=0, column=1, padx=10, pady=10)
account_balance_label.grid(row=0, column=0, padx=5, pady=5)
account_number_label.grid(row=1, column=0, padx=5, pady=5)
add_money_button.grid(row=2, column=0, padx=5, pady=5)
move_money_button.grid(row=3, column=0, padx=5, pady=5)

wallets_frame.grid(row=1, column=1, padx=10, pady=10)
primary_wallet_label.grid(row=0, column=0, padx=5, pady=5)
business_wallet_label.grid(row=1, column=0, padx=5, pady=5)

# Run the Tkinter main loop
root.mainloop()

if __name__ == '__main__':
    app.run(port=int(os.getenv('PORT', 3000)))



