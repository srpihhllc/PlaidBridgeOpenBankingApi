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
6. **Legal & Privacy Enforcement**: Lenders are **strictly prohibited from selling or sharing borrower financial data**. Borrowers engaging in **delinquency, fraud, or evasion** will be **penalized to the full extent of the law**.
7. **Termination**: This license automatically terminates if you violate any of these terms.

By using the Software, you agree to these terms.
"""

from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import csv
import pdfplumber
from bson import ObjectId
from fpdf import FPDF
from datetime import datetime, timedelta
import requests

# Load environment variables
load_dotenv()

# Flask app setup
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
todos_collection = db["todos"]

# Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global account balance
global_account_balance = 848583.68

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

# Calculate global balance
def calculate_global_balance():
    global global_account_balance
    account_data = accounts_collection.find()
    balance = sum(account.get('balance', 0) for account in account_data)
    return global_account_balance + balance

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.authenticate(username, password)
        
        if user:
            login_user(user)
            return redirect(url_for('account_info'))
        
        return jsonify({"message": "Invalid credentials"}), 401

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))  

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/account-info')
@login_required
def account_info():
    user_balance = accounts_collection.find_one({"user_id": current_user.id}, {"balance": 1}) or {"balance": 0}
    total_global_balance = calculate_global_balance()
    return render_template('account_info.html', account_balance=user_balance.get("balance"), global_balance=total_global_balance)

@app.route('/global_balance', methods=['GET'])
@login_required
def global_balance():
    return jsonify({"global_balance": calculate_global_balance()}), 200

@app.route('/link-borrower-account', methods=['POST'])
@login_required
def link_borrower_account():
    borrower_id = request.json.get("borrower_id")

    headers = {"Authorization": f"Bearer {os.getenv('PLAID_SECRET')}"}
    response = requests.post(os.getenv('PLAID_API_URL') + "/link/token/create", headers=headers, json={})

    if response.status_code == 200:
        return jsonify({"message": "Plaid link token generated", "link_token": response.json()["link_token"]}), 200

    return jsonify({"message": "Failed to generate Plaid link token"}), 400

@app.route('/todo_list')
@login_required
def todo_list():
    todos = list(todos_collection.find({"user_id": current_user.id}))
    return render_template("todos.html", todos=todos)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
