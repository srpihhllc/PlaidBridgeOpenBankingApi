from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, abort, render_template
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import os
import csv
import pdfplumber
import logging
from werkzeug.utils import secure_filename
from fpdf import FPDF
from plaid.api import plaid_api
from plaid.model import *
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from datetime import datetime, timedelta
from pymongo import MongoClient
import requests
from bson import ObjectId
from flask_wtf.csrf import CSRFProtect

# Load environment variables
load_dotenv()

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # Secure random key
if not app.secret_key:
    raise ValueError("SECRET_KEY environment variable must be set")

# CSRF Protection
csrf = CSRFProtect(app)

# Flask-SocketIO for real-time communication
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB setup
try:
    mongo_client = MongoClient(os.getenv('MONGO_CONNECTION_STRING'))
    db = mongo_client['open_banking_api']
    users_collection = db['users']
    accounts_collection = db['accounts']
    statements_collection = db['statements']
except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {e}")
    raise

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    """User class for Flask-Login."""
    def __init__(self, id, username=None, email=None):
        self.id = id
        self.username = username
        self.email = email

    @staticmethod
    def authenticate(username, password):
        user_data = users_collection.find_one({"username": username})
        if user_data and password == user_data.get('password'):  # Replace with secure password checking
            return User(str(user_data['_id']), username=user_data['username'])
        return None

@login_manager.user_loader
def load_user(user_id):
    """Load user from database."""
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_id, username=user_data.get('username'))
    return None

# Home route
@app.route('/')
@login_required
def home():
    return render_template('index.html')

# Account linking route
@app.route("/link-account")
@login_required
def link_account():
    return render_template('link_account.html')

# Example: Open Banking API abstraction
class OpenBankingAPI:
    """Abstract class for open banking API integrations."""
    def __init__(self, client_id, secret, base_url):
        self.client_id = client_id
        self.secret = secret
        self.base_url = base_url

    def authenticate(self):
        payload = {"client_id": self.client_id, "secret": self.secret}
        response = requests.post(f"{self.base_url}/auth", json=payload)
        response.raise_for_status()
        return response.json()

    def fetch_account_details(self, access_token):
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{self.base_url}/accounts", headers=headers)
        response.raise_for_status()
        return response.json()

# Manual linking attempt handler
@app.route('/manual_link_attempt', methods=['POST'])
@login_required
def manual_link_attempt():
    data = request.json
    accounts_collection.insert_one({
        "lender_id": current_user.id,
        "borrower_account": data.get('borrower_account'),
        "timestamp": datetime.utcnow()
    })
    socketio.emit('alert', {
        "message": f"Manual linking attempt detected by {current_user.username}",
        "timestamp": datetime.utcnow().isoformat()
    }, room='admin')
    return jsonify({'message': 'Manual linking attempt recorded'})

# Example: Fraud detection function
@app.route('/verify_mirror', methods=['POST'])
@login_required
def verify_mirror():
    borrower_account = request.json['borrower_account']
    mock_account = request.json['mock_account']
    if borrower_account == mock_account:
        return jsonify({'message': 'Accounts match'})
    return jsonify({'message': 'Account mismatch detected'}), 400

# Health check route
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "database": "connected" if mongo_client else "disconnected"}), 200

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        emit('message', {'info': f'User {current_user.username} connected'})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
