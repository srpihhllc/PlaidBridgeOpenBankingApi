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

# Plaid API integration
def get_plaid_link_token():
    headers = {"Authorization": f"Bearer {os.getenv('PLAID_SECRET')}"}
    response = requests.post(os.getenv('PLAID_API_URL') + "/link/token/create", headers=headers, json={})
    return response.json() if response.status_code == 200 else {"error": response.text}

# Borrower-lender identity verification
@app.route('/verify-identity', methods=['POST'])
@login_required
def verify_identity():
    lender_id = request.json.get("lender_id")
    borrower_id = request.json.get("borrower_id")
    
    lender_exists = accounts_collection.find_one({"_id": lender_id})
    borrower_exists = accounts_collection.find_one({"_id": borrower_id})
    
    if lender_exists and borrower_exists:
        return jsonify({"message": "Identity Verified"}), 200
    return jsonify({"message": "Identity Verification Failed"}), 400

# Lender account freeze/detachment feature
@app.route('/freeze-account', methods=['POST'])
@login_required
def freeze_account():
    account_id = request.json.get("account_id")
    result = accounts_collection.update_one({"_id": account_id}, {"$set": {"status": "frozen"}})
    return jsonify({"message": "Account frozen"}) if result.modified_count > 0 else jsonify({"message": "Freeze failed"}), 400

@app.route('/detach-account', methods=['POST'])
@login_required
def detach_account():
    account_id = request.json.get("account_id")
    result = accounts_collection.delete_one({"_id": account_id})
    return jsonify({"message": "Account detached"}) if result.deleted_count > 0 else jsonify({"message": "Detachment failed"}), 400

# Borrower account linking (locked until obligations are fulfilled)
@app.route('/link-borrower-account', methods=['POST'])
@login_required
def link_borrower_account():
    borrower_id = request.json.get("borrower_id")
    plaid_data = request.json.get("plaid_linked_account_data")

    accounts_collection.update_one(
        {"_id": borrower_id},
        {"$set": {"mock_account_linked": True, "linked_account": plaid_data}}
    )

    return jsonify({"message": "Borrower account linked to the mock API"}), 200

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

# Lender linking via Plaid
@app.route('/link-lender-account', methods=['POST'])
@login_required
def link_lender_account():
    lender_id = request.json.get("lender_id")
    plaid_data = request.json.get("plaid_linked_account_data")

    accounts_collection.update_one(
        {"_id": lender_id},
        {"$set": {"linked_account": plaid_data, "verified": True}}
    )

    return jsonify({"message": "Lender account linked and verified"}), 200

# Live-time statement retrieval (3-minute access limit)
@app.route('/get-borrower-statements', methods=['GET'])
@login_required
def get_borrower_statements():
    lender_id = current_user.id
    borrower_id = request.args.get("borrower_id")

    lender_data = accounts_collection.find_one({"_id": lender_id})
    if not lender_data or not lender_data.get("verified"):
        return jsonify({"message": "Lender verification required"}), 403

    borrower_data = accounts_collection.find_one({"_id": borrower_id}, {"statements": 1})

    if borrower_data:
        session_expiry = datetime.utcnow() + timedelta(minutes=3)
        return jsonify({"borrower_statements": borrower_data["statements"], "expiry_time": session_expiry.isoformat()}), 200

    return jsonify({"message": "No borrower found"}), 404

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)

