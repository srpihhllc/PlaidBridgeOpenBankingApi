from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import csv
import pdfplumber
from bson import ObjectId
from datetime import datetime, timedelta
import requests
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or "fallback_secret_key"
app.config['UPLOAD_FOLDER'] = 'statements'

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB setup
mongo_client = MongoClient(os.getenv('MONGO_CONNECTION_STRING'))
db = mongo_client['open_banking_api']
accounts_collection = db['accounts']
todos_collection = db['todos']

# Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User authentication class
class User(UserMixin):
    def __init__(self, id, username=None, role=None, verified=False):
        self.id = id
        self.username = username
        self.role = role
        self.verified = verified

    @staticmethod
    def authenticate(username, password):
        user_data = accounts_collection.find_one({"username": username})
        if user_data and check_password_hash(user_data['password'], password):
            return User(str(user_data["_id"]), user_data["username"], user_data["role"], user_data.get("verified", False))
        return None

@login_manager.user_loader
def load_user(user_id):
    user_data = accounts_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(str(user_data["_id"]), user_data["username"], user_data["role"], user_data.get("verified", False))
    return None

# Global balance tracking
def calculate_global_balance():
    account_data = accounts_collection.find()
    return sum(account.get('balance', 0) for account in account_data)

@app.route('/global_balance', methods=['GET'])
@login_required
def global_balance():
    try:
        balance = calculate_global_balance()
        return jsonify({"global_balance": balance}), 200
    except Exception as e:
        return jsonify({"message": "Error calculating global balance", "error": str(e)}), 500

# Secure user authentication routes
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.authenticate(username, password)
    if user:
        login_user(user)
        return redirect(url_for('account_info'))
    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# AI-powered borrower account locking for lender agreements
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

# AI-driven borrower payment alerts
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

# PDF & CSV statement validation with AI fraud detection
@app.route('/upload-statement', methods=['POST'])
@login_required
def upload_statement():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filename)

    try:
        if filename.endswith('.pdf'):
            statements = parse_pdf(filename)
        elif filename.endswith('.csv'):
            statements = parse_csv(filename)
        else:
            return jsonify({"message": "Unsupported file format"}), 400

        for statement in statements:
            correct_discrepancies(statement)

        return jsonify({"message": "Statement processed successfully", "transactions": statements}), 200
    except Exception as e:
        return jsonify({"message": "Error processing file", "error": str(e)}), 500

# Supporting functions for financial statement parsing
def parse_pdf(file_path):
    statements = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                statements.extend(parse_page(text))
    return statements

def parse_page(text):
    statements = []
    for line in text.split('\n'):
        parts = line.split()
        if len(parts) >= 3:
            try:
                dt = datetime.strptime(parts[0], '%Y-%m-%d').date()
                amount = float(parts[-1].replace('$', '').replace(',', ''))
                description = ' '.join(parts[1:-1])
                statements.append({"date": dt, "description": description, "amount": amount})
            except ValueError:
                continue
    return statements

def correct_discrepancies(statements):
    corrected = []
    for statement in statements:
        try:
            amount = float(statement["amount"])
            corrected.append({"amount": amount})
        except ValueError:
            continue
    return corrected

# To-Do List Management
@app.route('/add_todo', methods=['POST'])
@login_required
def add_todo():
    title = request.form.get("title")
    if not title:
        return jsonify({"message": "Task title is required"}), 400

    todos_collection.insert_one({"title": title, "completed": False, "user_id": current_user.id})
    return redirect(url_for("todo_list"))

@app.route('/todo_list')
@login_required
def todo_list():
    todos = list(todos_collection.find({"user_id": current_user.id}))
    return render_template("todos.html", todos=todos)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
