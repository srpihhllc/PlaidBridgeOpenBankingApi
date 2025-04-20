from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import csv
import pdfplumber
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

# Initialize Flask-SocketIO (for real-time event updates)
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

# Global account balance (starting value)
global_account_balance = 848583.68

# User class for authentication and session management
class User(UserMixin):
    def __init__(self, id, username=None):
        self.id = id
        self.username = username

    @staticmethod
    def authenticate(username, password):
        # Example user lookup; replace with a secure DB lookup as needed
        user_data = {"username": "test_user", "password": "test_password"}
        if username == user_data["username"] and password == user_data["password"]:
            return User("1", username=user_data["username"])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Calculate the global balance by summarizing individual account balances
def calculate_global_balance():
    global global_account_balance
    account_data = accounts_collection.find()
    balance = sum(account.get('balance', 0) for account in account_data)
    return global_account_balance + balance

# Treasury Prime API integration
def get_treasury_prime_accounts():
    headers = {"Authorization": f"Bearer {os.getenv('TREASURY_PRIME_API_KEY')}"}
    response = requests.get(os.getenv('TREASURY_PRIME_API_URL') + "/accounts", headers=headers)
    return response.json() if response.status_code == 200 else {"error": response.text}

# Plaid API integration for generating a link token
def get_plaid_link_token():
    headers = {"Authorization": f"Bearer {os.getenv('PLAID_SECRET')}"}
    response = requests.post(os.getenv('PLAID_API_URL') + "/link/token/create", headers=headers, json={})
    return response.json() if response.status_code == 200 else {"error": response.text}

# CSV to PDF conversion (produces a polished PDF statement)
def convert_csv_to_pdf(csv_file, pdf_file):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    with open(csv_file, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            row_text = ", ".join(row)
            pdf.cell(200, 10, txt=row_text, ln=True)
    pdf.output(pdf_file)
    return pdf_file

# Borrower-lender identity verification endpoint
@app.route('/verify-identity', methods=['POST'])
@login_required
def verify_identity():
    lender_id = request.json.get("lender_id")
    borrower_id = request.json.get("borrower_id")
    
    lender_exists = accounts_collection.find_one({"_id": lender_id})
    borrower_exists = accounts_collection.find_one({"_id": borrower_id})
    
    if lender_exists and borrower_exists:
        # Emit a real-time event to inform connected clients of successful verification
        socketio.emit('identity_verified', {'lender_id': lender_id, 'borrower_id': borrower_id})
        return jsonify({"message": "Identity Verified"}), 200
    return jsonify({"message": "Identity Verification Failed"}), 400

# Lender-initiated account freeze endpoint
@app.route('/freeze-account', methods=['POST'])
@login_required
def freeze_account():
    account_id = request.json.get("account_id")
    result = accounts_collection.update_one({"_id": account_id}, {"$set": {"status": "frozen"}})
    if result.modified_count > 0:
        socketio.emit('account_status_update', {'account_id': account_id, 'status': 'frozen'})
        return jsonify({"message": "Account frozen"}), 200
    return jsonify({"message": "Freeze failed"}), 400

# Lender-initiated account detachment endpoint
@app.route('/detach-account', methods=['POST'])
@login_required
def detach_account():
    account_id = request.json.get("account_id")
    result = accounts_collection.delete_one({"_id": account_id})
    if result.deleted_count > 0:
        socketio.emit('account_detached', {'account_id': account_id})
        return jsonify({"message": "Account detached"}), 200
    return jsonify({"message": "Detachment failed"}), 400

# Home page route (requires login)
@app.route('/')
@login_required
def home():
    return render_template('index.html')

# Account information route displaying both user and global balances
@app.route('/account-info')
@login_required
def account_info():
    global global_account_balance
    user_balance_doc = accounts_collection.find_one({"user_id": current_user.id}, {"balance": 1}) or {"balance": 0}
    user_balance = user_balance_doc.get("balance", 0)
    total_global_balance = calculate_global_balance()
    return render_template('account_info.html', account_balance=user_balance, global_balance=total_global_balance)

# Returns the calculated global balance
@app.route('/global_balance', methods=['GET'])
@login_required
def global_balance():
    try:
        balance = calculate_global_balance()
        return jsonify({"global_balance": balance}), 200
    except Exception as e:
        return jsonify({"message": "Error calculating global balance", "error": str(e)}), 500

# Endpoint to upload and process imperfect bank statement PDFs
@app.route('/upload-pdf', methods=['POST'])
@login_required
def upload_pdf():
    global global_account_balance
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filename)

    try:
        # Parse the PDF and simulate correction of discrepancies
        statements = parse_pdf(filename)
        account_updates = correct_discrepancies(statements)
        for update in account_updates:
            global_account_balance += float(update["amount"])
        # Emit event indicating PDF processing completion
        socketio.emit('pdf_processed', {'new_balance': global_account_balance})
        return jsonify({"message": "PDF processed successfully", "account_balance": global_account_balance}), 200
    except Exception as e:
        return jsonify({"message": "Error processing file", "error": str(e)}), 500

# Endpoint to upload CSV files and convert them to perfect PDF statements
@app.route('/upload-csv', methods=['POST'])
@login_required
def upload_csv():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    csv_filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(csv_filename)
    try:
        pdf_filename = os.path.splitext(csv_filename)[0] + ".pdf"
        convert_csv_to_pdf(csv_filename, pdf_filename)
        socketio.emit('csv_converted', {'pdf_file': pdf_filename})
        return jsonify({"message": "CSV converted to PDF successfully", "pdf_file": pdf_filename}), 200
    except Exception as e:
        return jsonify({"message": "Error converting CSV to PDF", "error": str(e)}), 500

# Endpoint for Treasury Prime account retrieval (for integration testing)
@app.route('/treasury-prime-accounts', methods=['GET'])
@login_required
def treasury_prime_accounts():
    data = get_treasury_prime_accounts()
    return jsonify(data), 200

# Endpoint for Plaid link token generation (for integration testing)
@app.route('/plaid-link-token', methods=['GET'])
@login_required
def plaid_link_token():
    data = get_plaid_link_token()
    return jsonify(data), 200

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    status = "connected" if mongo_client else "disconnected"
    return jsonify({"status": "healthy", "database": status}), 200

# Supporting functions for parsing and correcting PDFs
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
    """Parse the text of a single PDF page to extract date, description, and amount."""
    statements = []
    for line in text.split("\n"):
        parts = line.split()
        if len(parts) >= 3:
            try:
                dt = datetime.strptime(parts[0], "%Y-%m-%d").date()
                amount = float(parts[-1].replace("$", "").replace(",", ""))
                description = " ".join(parts[1:-1])
                statements.append({"date": dt, "description": description, "amount": amount})
            except ValueError:
                continue
    return statements

def correct_discrepancies(statements):
    """Simulate correction of transaction discrepancies (miscalculations, spelling errors, etc.)."""
    corrected = []
    for stmt in statements:
        try:
            amt = float(stmt["amount"])
            corrected.append({"amount": amt})
        except ValueError:
            continue
    return corrected

# Login endpoint (renders a login page or processes credentials)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.authenticate(username, password)
        if user:
            login_user(user)
            socketio.emit('login_success', {'user': user.username})
            return redirect(url_for('account_info'))
        return jsonify({"message": "Invalid credentials"}), 401
    return render_template('login.html')

# Logout endpoint
@app.route('/logout')
@login_required
def logout():
    logout_user()
    socketio.emit('logout', {'user': current_user.username})
    return redirect(url_for('login'))

# Run the app using SocketIO for real-time updates
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
