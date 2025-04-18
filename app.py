from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, logging
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import csv
import pdfplumber
from bson import ObjectId
from fpdf import FPDF
from datetime import datetime
import requests

# Load environment variables
load_dotenv()

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or "fallback_secret_key"
app.config['UPLOAD_FOLDER'] = 'statements'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB setup
try:
    mongo_client = MongoClient(os.getenv('MONGO_CONNECTION_STRING'))
    db = mongo_client['open_banking_api']
    accounts_collection = db['accounts']
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    raise

# Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global account balance
global_account_balance = 848583.68  # Original balance

# User class for authentication
class User(UserMixin):
    def __init__(self, id, username=None):
        self.id = id
        self.username = username

    @staticmethod
    def authenticate(username, password):
        # Example user lookup
        user_data = {"username": "test_user", "password": "test_password"}
        if username == user_data["username"] and password == user_data["password"]:
            return User("1", username=user_data["username"])
        return None

@login_manager.user_loader
def load_user(user_id):
    # Load the user from session
    return User(user_id)

# Calculate global balance
def calculate_global_balance():
    global global_account_balance
    account_data = accounts_collection.find()
    balance = sum(account.get('balance', 0) for account in account_data)
    return global_account_balance + balance

# Login Route Added
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
    return redirect(url_for('login'))  # 🛠️ FIXED

                    
# Routes
@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/account-info')
@login_required
def account_info():
    global global_account_balance
    user_balance = accounts_collection.find_one({"user_id": current_user.id}, {"balance": 1}) or {"balance": 0}
    user_balance = user_balance.get("balance")
    total_global_balance = calculate_global_balance()
    return render_template('account_info.html', account_balance=user_balance, global_balance=total_global_balance)

@app.route('/global_balance', methods=['GET'])
@login_required
def global_balance():
    try:
        balance = calculate_global_balance()
        return jsonify({"global_balance": balance}), 200
    except Exception as e:
        return jsonify({"message": "Error calculating global balance", "error": str(e)}), 500

@app.route('/upload-pdf', methods=['POST'])
@login_required
def upload_pdf():
    global global_account_balance
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        try:
            # Parse PDF
            statements = parse_pdf(filename)
            account_updates = correct_discrepancies(statements)

            for update in account_updates:
                global_account_balance += float(update["amount"])

            return jsonify({"message": "PDF processed successfully", "account_balance": global_account_balance}), 200
        except Exception as e:
            return jsonify({"message": "Error processing file", "error": str(e)}), 500
    return jsonify({"message": "Invalid file format"}), 400

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "database": "connected" if mongo_client else "disconnected"}), 200

# Supporting functions
def parse_pdf(file_path):
    """Parse the PDF and extract financial transactions."""
    statements = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                statements.extend(parse_page(text))
    return statements

def parse_page(text):
    """Parse the text of a single PDF page."""
    statements = []
    for line in text.split('\n'):
        parts = line.split()
        if len(parts) >= 3:
            try:
                date = datetime.strptime(parts[0], '%Y-%m-%d').date()
                amount = float(parts[-1].replace('$', '').replace(',', ''))
                description = ' '.join(parts[1:-1])
                transaction = {
                    "date": date,
                    "description": description,
                    "amount": amount
                }
                statements.append(transaction)
            except ValueError:
                continue
    return statements

def correct_discrepancies(statements):
    """Simulate correction of transaction discrepancies."""
    corrected = []
    for statement in statements:
        try:
            amount = float(statement["amount"])
            corrected.append({"amount": amount})
        except ValueError:
            continue
    return corrected

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
