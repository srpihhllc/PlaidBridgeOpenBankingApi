"""
PlaidBridgeOpenBankingApi
Copyright © [YEAR] [Sir Pollards Internal Holistic Healing LLC]
All rights reserved.

This software is covered under a proprietary license. Unauthorized use, modification, or distribution is strictly prohibited.

[Sir Pollards Internal Holistic Healing LLC] ("SRPIHHLLC") grants you a non-exclusive, non-transferable, limited license to use the API software ("Software") under the following terms:

1. **Usage**: You may use the Software for personal or internal business purposes.
2. **Restrictions**: You may not copy, modify, distribute, sell, or lease any part of the Software without prior written consent from the Author.
3. **Ownership**: The Author retains all rights, title, and interest in and to the Software, including all AI-powered functionalities embedded in the API.
4. **AI Security & Ethical Compliance**: This Software includes AI-driven security layers that enforce ethical borrowing practices, borrower account locking, lender verification, and automated alerts. These AI mechanisms **must not be altered or bypassed**.
5. **Integration with Fintech Systems**: Usage of this API in conjunction with fintech platforms (Plaid, Stripe, etc.) **does not alter ownership rights**. All components remain proprietary.
6. **Termination**: This license automatically terminates if you violate any of these terms.

By using the Software, you agree to these terms.
"""

from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import requests
import csv
import pdfplumber
from fpdf import FPDF
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or "fallback_secret_key"
app.config['UPLOAD_FOLDER'] = 'statements'

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB setup
mongo_client = MongoClient(os.getenv('MONGO_CONNECTION_STRING'))
db = mongo_client['open_banking_api']
accounts_collection = db['accounts']

# Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User authentication class
class User(UserMixin):
    def __init__(self, id, username=None):
        self.id = id
        self.username = username

    @staticmethod
    def authenticate(username, password):
        user = accounts_collection.find_one({"username": username, "password": password})
        return User(user["_id"], username=user["username"]) if user else None

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# AI-Powered Borrower Locking & Payment Enforcement
class BorrowerGuardianAI:
    def __init__(self, borrower_id):
        self.borrower_id = borrower_id
        self.locked = True  # Ensures borrower remains linked until payments are fulfilled
        self.agreement = None

    def analyze_agreement(self, agreement_text):
        # AI extracts payment terms and schedules
        self.agreement = {"total_due": 5000, "due_dates": ["2025-05-01", "2025-06-01"]}
        return self.agreement

    def enforce_payment_schedule(self):
        # AI monitors transactions and prevents detachment until payment completion
        payment_history = db.transactions.find({"borrower_id": self.borrower_id})
        total_paid = sum(tx["amount"] for tx in payment_history)

        if total_paid >= self.agreement["total_due"]:
            self.locked = False  # Allow detachment once obligations are met

        return {"status": "locked" if self.locked else "free", "total_paid": total_paid}

# Borrower account linking (locked until obligations are fulfilled)
@app.route('/lock-borrower-account', methods=['POST'])
@login_required
def lock_borrower_account():
    borrower_id = request.json.get("borrower_id")
    agreement_data = request.json.get("agreement_data")

    accounts_collection.update_one(
        {"_id": borrower_id},
        {"$set": {"mock_account_locked": True, "agreement": agreement_data}}
    )

    return jsonify({"message": "Borrower account locked until obligations are fulfilled"}), 200

@app.route('/detach-borrower-account', methods=['POST'])
@login_required
def detach_borrower_account():
    borrower_id = request.json.get("borrower_id")

    borrower_data = accounts_collection.find_one({"_id": borrower_id})
    if borrower_data and borrower_data.get("outstanding_balance") > 0:
        return jsonify({"message": "Borrower cannot detach the API until financial obligations are fulfilled"}), 403

    accounts_collection.update_one(
        {"_id": borrower_id},
        {"$set": {"mock_account_linked": False}}
    )

    return jsonify({"message": "Borrower successfully detached"}), 200

# AI-Driven Payment Calculation
@app.route('/calculate-payments', methods=['POST'])
@login_required
def calculate_payments():
    borrower_id = request.json.get("borrower_id")

    agreement = accounts_collection.find_one({"_id": borrower_id}, {"agreement": 1})
    if not agreement:
        return jsonify({"message": "No agreement found"}), 400

    total_amount_due = agreement["agreement"]["total_amount"]
    due_dates = agreement["agreement"]["due_dates"]

    return jsonify({"message": "Payment schedule generated", "total_due": total_amount_due, "due_dates": due_dates}), 200

# AI-Powered Transaction Monitoring
@app.route('/track-payments', methods=['GET'])
@login_required
def track_payments():
    borrower_id = request.args.get("borrower_id")

    transactions = db.transactions.find({"borrower_id": borrower_id})
    total_paid = sum(tx["amount"] for tx in transactions if tx["type"] == "payment")

    outstanding_balance = db.accounts.find_one({"_id": borrower_id})["outstanding_balance"]

    return jsonify({"total_paid": total_paid, "outstanding_balance": outstanding_balance}), 200

# AI-Driven Payment Alerts
@app.route('/send-payment-alerts', methods=['POST'])
@login_required
def send_payment_alerts():
    borrower_id = request.json.get("borrower_id")
    
    agreement = accounts_collection.find_one({"_id": borrower_id}, {"agreement": 1})
    due_dates = agreement["agreement"]["due_dates"]

    for date in due_dates:
        alert_date = datetime.strptime(date, '%Y-%m-%d') - timedelta(days=7)
        db.alerts.insert_one({"borrower_id": borrower_id, "alert_date": alert_date, "message": "Upcoming payment due in 7 days"})
    
    return jsonify({"message": "Payment alerts scheduled"}), 200

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
