from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import requests
import csv
import pdfplumber
from fpdf import FPDF
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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

# Global account balance (starting value)
global_account_balance = 848583.68  # This should be in the database, not a global

# User class for authentication and session management
class User(UserMixin):
    def __init__(self, id, username=None, role=None, verified=False):
        self.id = id
        self.username = username
        self.role = role  # 'lender' or 'borrower'
        self.verified = verified

    @staticmethod
    def authenticate(username, password):
        user_data = accounts_collection.find_one({"username": username})
        if user_data and check_password_hash(user_data['password'], password):
            return User(
                str(user_data["_id"]),
                username=user_data["username"],
                role=user_data["role"],
                verified=user_data.get("verified", False)
            )
        return None

@login_manager.user_loader
def load_user(user_id):
    user_data = accounts_collection.find_one({"_id": user_id})
    if user_data:
        return User(
            str(user_data["_id"]),
            username=user_data["username"],
            role=user_data["role"],
            verified=user_data.get("verified", False)
        )
    return None

# Calculate the global balance by summarizing individual account balances
def calculate_global_balance():
    account_data = accounts_collection.find()
    balance = sum(account.get('balance', 0) for account in account_data)
    return balance  # Do not add to a global here.  Return the calculated value

# Plaid API integration for generating a link token
def get_plaid_link_token(client_user_id):
    """
    Generates a Plaid link token for account linking.

    Args:
        client_user_id (str):  Unique ID for the user linking their account.
    """
    headers = {"Authorization": f"Bearer {os.getenv('PLAID_SECRET')}"}
    payload = {
        "client_name": "Open Banking Mock API",  # Customizable
        "user": {"client_user_id": client_user_id},
        "products": ["auth", "transactions"],  #  adjust as necessary
        "country_codes": ["US"],  #  adjust as necessary
    }
    response = requests.post(os.getenv('PLAID_API_URL') + "/link/token/create", headers=headers, json=payload)
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

#  Lender verification endpoint using bank account linking
@app.route('/verify-lender-account', methods=['POST'])
@login_required
def verify_lender_account():
    """
    Lenders must link their bank account to verify their identity.
    """
    data = request.json
    required_fields = ["plaid_link_token"]  # Expecting the Plaid link token
    missing = [field for field in required_fields if field not in data or not data[field]]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400

    #  In a real-world scenario, you would exchange the Plaid token
    #  for an access token and store that, along with other account details.
    #  For this mock, we'll just update the user's verification status.
    #  You would typically get account details and store them.
    current_user.verified = True
    accounts_collection.update_one(
        {"_id": current_user.id},
        {"$set": {"verified": True}}
    )
    socketio.emit('lender_verified', {'user': current_user.username})
    return jsonify({"message": "Lender verified successfully"}), 200

# Borrower account linking
@app.route('/link-borrower-account', methods=['POST'])
@login_required
def link_borrower_account():
    """
    Borrowers link their bank account using Plaid.
    """
    borrower_id = current_user.id  # The current user is the borrower
    plaid_link_token = request.json.get("plaid_link_token") # Get link token from request

    if not plaid_link_token:
        return jsonify({"message": "Plaid link token is required"}), 400

    # Again, in real app exchange the token.  Here, just update status.
    accounts_collection.update_one(
        {"_id": borrower_id},
        {"$set": {"verified": True, "plaid_link_token": plaid_link_token}}  # Store Plaid data
    )
    socketio.emit('borrower_account_linked', {'user': current_user.username})
    return jsonify({"message": "Borrower account linked successfully"}), 200

# Home page route (requires login)
@app.route('/')
@login_required
def home():
    return render_template('index.html')

# Account information route displaying both user and global balances
@app.route('/account-info')
@login_required
def account_info():
    user_balance_doc = accounts_collection.find_one({"_id": current_user.id}, {"balance": 1}) or {"balance": 0}
    user_balance = user_balance_doc.get("balance", 0)
    global_balance = calculate_global_balance()  # Call the function
    return render_template('account_info.html', account_balance=user_balance, global_balance=global_balance)

# Returns the calculated global balance
@app.route('/global_balance', methods=['GET'])
@login_required
def global_balance():
    try:
        balance = calculate_global_balance()  # Call the function
        return jsonify({"global_balance": balance}), 200
    except Exception as e:
        return jsonify({"message": "Error calculating global balance", "error": str(e)}), 500

# Endpoint to upload and process bank statement PDFs and CSVs
@app.route('/upload-statement', methods=['POST'])
@login_required
def upload_statement():
    """Handles upload and processing of bank statements (PDF or CSV)."""
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filename)  # Save the uploaded file

    try:
        if filename.endswith('.pdf'):
            statements = parse_pdf(filename)
        elif filename.endswith('.csv'):
            statements = parse_csv(filename)
        else:
            return jsonify({"message": "Unsupported file format"}), 400

        #  Here you would process the statements, correct discrepancies,
        #  and store the data in the database.  For this mock, we'll
        #  just return the extracted statements.
        #  You might also update account balances here.

        # Example (replace with your actual processing logic):
        # for statement in statements:
        #     correct_discrepancies(statement) #  correct any discrepancies
        #     store_transaction(statement)  # Store in DB
        #     update_account_balance(statement) # Update Balances

        socketio.emit('statement_processed', {'message': 'Statement processed', 'filename': file.filename})
        return jsonify({"message": "Statement processed successfully", "transactions": statements}), 200  # Return extracted data
    except Exception as e:
        return jsonify({"message": "Error processing file", "error": str(e)}), 500
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
def parse_csv(file_path):
    """Parse the CSV and extract financial transactions."""
    statements = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                date_str = row.get("Date")
                if not date_str:
                    continue
                dt = datetime.strptime(date_str, '%Y-%m-%d').date()
                amount_str = row.get("Amount")
                if not amount_str:
                    continue
                amount = float(amount_str.replace('$', '').replace(',', ''))
                description = row.get("Description", "")  # Default to empty string if missing
                statements.append({"date": dt, "description": description, "amount": amount})
            except ValueError:
                continue  # Skip rows with invalid date or amount
            except KeyError as e:
                print(f"KeyError: {e}.  Row: {row}")
                continue
    return statements

# Endpoint for Plaid link token generation
@app.route('/plaid-link-token', methods=['GET'])
@login_required
def plaid_link_token_endpoint():
    """
    Endpoint to generate a Plaid link token for the current user.
    """
    user_id = current_user.id
    token_response = get_plaid_link_token(user_id)  # Pass user ID
    if "error" in token_response:
        return jsonify(token_response), 500
    return jsonify(token_response), 200

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    status = "connected" if mongo_client else "disconnected"
    return jsonify({"status": "healthy", "database": status}), 200

# Login endpoint (renders a login page or processes credentials)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.authenticate(username, password)
        if user:
            login_user(user)
            #  No login_success event here.  Do it on the next page load.
            return redirect(url_for('account_info'))
        return jsonify({"message": "Invalid credentials"}), 401
    return render_template('login.html')

# Logout endpoint
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Function to simulate sending transaction data to lender (mock)
def send_transaction_data(lender_id, borrower_id, transaction_data):
    """
    Mocks sending transaction data to a lender.  In a real application,
    this would involve sending data to the lender's system (e.g., via API).
    """
    #  This is a placeholder.  Replace with your actual data sending logic.
    print(f"Sending transaction data to lender {lender_id} for borrower {borrower_id}:")
    print(transaction_data)
    socketio.emit('transaction_data_sent', {
        'lender_id': lender_id,
        'borrower_id': borrower_id,
        'transaction_count': len(transaction_data)
    })

@app.route('/get-borrower-transactions', methods=['GET'])
@login_required
def get_borrower_transactions():
    """
    Retrieves a borrower's transactions for a lender to review.
    """
    lender_id = current_user.id
    borrower_id = request.args.get('borrower_id')

    #  Verify that the lender is allowed to access this borrower's data
    lender_data = accounts_collection.find_one({"_id": lender_id, "role": "lender"})
    borrower_data = accounts_collection.find_one({"_id": borrower_id, "role": "borrower"})

    if not lender_data or not lender_data.get("verified"):
        return jsonify({"message": "Lender not verified"}), 403

    if not borrower_data:
        return jsonify({"message": "Borrower not found"}), 404

    #  In a real application, you would retrieve transactions from the database
    #  associated with the borrower.  For this mock, we'll return some dummy data.
    transactions = [
        {"date": "2024-01-15", "description": "Grocery Store", "amount": -75.20},
        {"date": "2024-01-14", "description": "Paycheck", "amount": 1200.00},
        {"date": "2024-01-10", "description": "Dinner", "amount": -30.00},
    ]  # Replace with actual data retrieval

    #  Send the transaction data to the lender (mock function)
    send_transaction_data(lender_id, borrower_id, transactions)

    return jsonify({"transactions": transactions}), 200
@app.route('/create-user', methods=['POST'])
def create_user():
    """
    Creates a new user (borrower or lender).  This is for initial setup.
    """
    username = request.json.get('username')
    password = request.json.get('password')
    role = request.json.get('role')  # "lender" or "borrower"

    if not username or not password or not role:
        return jsonify({"message": "Missing required fields"}), 400

    if role not in ('lender', 'borrower'):
        return jsonify({"message": "Invalid role. Must be 'lender' or 'borrower'"}), 400

    existing_user = accounts_collection.find_one({"username": username})
    if existing_user:
        return jsonify({"message": "Username already exists"}), 400

    hashed_password = generate_password_hash(password, method='sha256')
    user_data = {
        "username": username,
        "password": hashed_password,
        "role": role,
        "verified": False,  # Start as not verified
        "balance": 0,  # Initialize balance
    }
    result = accounts_collection.insert_one(user_data)
    user_id = result.inserted_id

    #  Log the user in immediately upon creation.
    user = User(str(user_id), username=username, role=role)
    login_user(user)  # Auto-login

    socketio.emit('user_created', {'username': username, 'role': role})
    return jsonify({"message": f"User created successfully.  You are now logged in as {username}."}), 201

# Run the app using SocketIO for real-time updates
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
