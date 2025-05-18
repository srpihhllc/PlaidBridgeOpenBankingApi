"""
Financial Powerhouse API
-------------------------
This API serves as a secure intermediary between lenders and borrowers.
It enforces ethical lending through AI-driven compliance, fraud detection,
smart contract automation, real-time financial health monitoring, multi-currency lending, 
and integration with major fintech platforms.
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv  # ✅ Load environment variables from .env

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize Flask app (Only once)
app = Flask(__name__)

# ✅ Configuration settings
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')

# ✅ Initialize extensions (Only once)
db = SQLAlchemy(app)
jwt = JWTManager(app)

# ✅ Fixed Flask-Limiter Initialization (Correct Argument Order)
limiter = Limiter(
    key_func=get_remote_address,  # ✅ Correctly passes `key_func` argument
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
limiter.init_app(app)  # ✅ Attach limiter separately to Flask app

# ✅ Configure Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------------------
# Health Check Endpoint
# ---------------------------
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# ---------------------------
# App Initialization & Run
# ---------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # ✅ Initializes all defined tables
    app.run(host='0.0.0.0', port=5000, debug=True)



# ---------------------------
# (Optional) User Model
# ---------------------------
# NOTE: A user model is needed for foreign key references (e.g., lender_id, borrower_id).
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)  # Store hashed passwords

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "User already exists"}), 400

    user = User(username=username)
    user.set_password(password)  # Store hashed password
    db.session.add(user)
    db.session.commit()

    return jsonify({"msg": "User created"}), 201

# ---------------------------
# 2. AI-Powered Compliance & Ethical Lending Enforcement
# ---------------------------
class LoanAgreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    terms = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="active")  
    ai_flagged = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)  # ✅ NEW: Account locking field
    violation_count = db.Column(db.Integer, default=0)  # ✅ Tracks compliance violations

def analyze_loan_agreement(agreement_text):
    """AI analyzes loan agreements for compliance and ethical standards."""
    unethical_terms = ["hidden fees", "predatory interest rates", "undisclosed penalties"]
    for term in unethical_terms:
        if term in agreement_text.lower():
            return {"status": "flagged", "reason": f"Contains unethical term: {term}"}
    return {"status": "approved"}

@app.route('/review_agreement', methods=['POST'])
@jwt_required()
def review_agreement():
    """AI scans and verifies loan agreements, locking borrower accounts upon excessive violations."""
    data = request.json
    borrower_id = data.get('borrower_id')
    agreement_text = data.get('terms', '')
    
    result = analyze_loan_agreement(agreement_text)
    borrower_agreements = LoanAgreement.query.filter_by(borrower_id=borrower_id).all()
    
    if result["status"] == "flagged":
        for agreement in borrower_agreements:
            agreement.violation_count += 1
            if agreement.violation_count >= 3:  # ✅ Lock account after 3 violations
                agreement.locked = True
        db.session.commit()

    return jsonify(result), 200

def generate_compliance_report(agreements):
    """Creates a compliance report for loan agreements flagged by AI."""
    flagged = [ag for ag in agreements if ag.ai_flagged]
    if flagged:
        return {"status": "report_generated", "violations": [ag.id for ag in flagged]}
    return {"status": "compliant"}

@app.route('/compliance_report', methods=['GET'])
@jwt_required()
def compliance_report():
    """Generates a compliance report based on loan agreements."""
    agreements = LoanAgreement.query.all()
    report = generate_compliance_report(agreements)
    return jsonify(report), 200

# ---------------------------
# 3. AI-Driven Financial Security & Fraud Prevention
# ---------------------------
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    ai_verified = db.Column(db.Boolean, default=False)

def detect_fraudulent_transaction(description, amount):
    """Flags potentially fraudulent transactions based on patterns."""
    suspicious_terms = ["unexpected large withdrawal", "account drained", "unauthorized payment"]
    if amount > 5000 or any(term in description.lower() for term in suspicious_terms):
        return True
    return False

@app.route('/validate_transaction', methods=['POST'])
@jwt_required()
def validate_transaction():
    """Flags fraudulent transactions and auto-locks borrower accounts on severe fraud detection."""
    data = request.json
    borrower_id = data.get('user_id')
    
    fraud_detected = detect_fraudulent_transaction(data.get('description', ''), data.get('amount', 0))
    
    if fraud_detected:
        borrower_agreements = LoanAgreement.query.filter_by(borrower_id=borrower_id).all()
        for agreement in borrower_agreements:
            agreement.locked = True  # ✅ Auto-locking borrower account upon fraud detection
        db.session.commit()
        return jsonify({"status": "locked", "message": "Transaction blocked—borrower account locked due to fraud."}), 403

    return jsonify({"fraudulent": fraud_detected}), 200

# ---------------------------
# 4. Borrower-Lender Smart Financial Integration
# ---------------------------
@app.route('/link_borrower_account', methods=['POST'])
@jwt_required()
def link_borrower_account():
    """Allows borrowers to link their accounts securely for lender access."""
    data = request.json
    # Implement actual verification logic here
    borrower_verified = True  
    if borrower_verified:
        return jsonify({"status": "linked", "message": "Borrower account successfully linked"}), 200
    return jsonify({"status": "failed", "message": "Verification required"}), 400

@app.route('/unlink_borrower_account', methods=['POST'])
@jwt_required()
def unlink_borrower_account():
    """
    Endpoint to unlink a borrower account.
    Blocking unlinking if the account is currently locked due to an active, accepted loan agreement.
    """
    data = request.json
    borrower_id = data.get('borrower_id')
    
    # Check if the borrower has any active agreements still locked
    locked_agreements = LoanAgreement.query.filter_by(borrower_id=borrower_id, locked=True).count()
    if locked_agreements > 0:
        return jsonify({
            "status": "blocked",
            "message": "Cannot unlink account until all loan obligations are met."
        }), 403
    
    # Proceed with unlinking logic (not shown)
    return jsonify({"status": "unlinked", "message": "Borrower account unlinked successfully."}), 200

# ---------------------------
# 5. AI-Powered PDF Statement Processing & Transaction Verification
# ---------------------------
@app.route('/upload_statement', methods=['POST'])
@jwt_required()
def upload_statement():
    """Processes bank statements via PDF, extracts text, and performs basic transaction verification."""
    if 'file' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400
    file = request.files['file']
    try:
        with pdfplumber.open(file) as pdf:
            extracted_text = pdf.pages[0].extract_text()
    except Exception as e:
        return jsonify({'message': f'Error processing PDF: {str(e)}'}), 500
    # AI-based corrections to miscalculations/spellings can be added here.
    return jsonify({'message': 'Statement processed successfully', 'extracted_text': extracted_text}), 200

# ---------------------------
# 6. Seamless Fintech API Integration (with Plaid)
# ---------------------------
import os
import logging
from dotenv import load_dotenv  # ✅ Added dotenv for loading environment variables
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, jwt_required
import plaid
from plaid.api_client import ApiClient
from plaid.configuration import Configuration
from plaid.api.plaid_api import PlaidApi
from plaid.model.link_token_create_request import LinkTokenCreateRequest

# ✅ Load environment variables from .env file
load_dotenv()

# Initialize Flask app (if not already initialized in your project)
app = Flask(__name__)

# ----- JWT Setup -----
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your_jwt_secret')
jwt = JWTManager(app)

# ----- Plaid API Credentials & Environment -----
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox').lower()

if not PLAID_CLIENT_ID or not PLAID_SECRET:
    raise Exception(f"PLAID_CLIENT_ID: {PLAID_CLIENT_ID}, PLAID_SECRET: {PLAID_SECRET} must be defined in your environment.")

# Determine the host based on the environment using Plaid's built-in environments.
if PLAID_ENV == 'sandbox':
    from plaid.configuration import Environment
    host = Environment.Sandbox
elif PLAID_ENV == 'development':
    host = plaid.Environment.Development
elif PLAID_ENV == 'production':
    host = plaid.Environment.Production
else:
    logging.warning("Unknown PLAID_ENV; defaulting to Sandbox.")
    host = plaid.Environment.Sandbox

# ----- Plaid API Configuration -----
configuration = Configuration(
    host=host,
    api_key={
        "clientId": PLAID_CLIENT_ID,  # Some versions may require "client_id" – verify per your docs.
        "secret": PLAID_SECRET
    }
)

# Initialize the Plaid API client.
api_client = ApiClient(configuration)
plaid_client = PlaidApi(api_client)

# ----- Plaid Link Token Generation Endpoint -----
@app.route('/generate_link_token', methods=['GET'])
@jwt_required()
def generate_link_token():
    """
    Generates a Plaid Link token for open banking integration.
    This endpoint is protected by JWT.
    """
    try:
        request_body = LinkTokenCreateRequest(
            client_name="PlaidBridge Open Banking API",
            language="en",
            country_codes=["US"],
            user={"client_user_id": "unique-user-id"},  # Replace with dynamic user id as needed.
            products=["auth", "transactions"]
        )
        response = plaid_client.link_token_create(request_body)
        return jsonify({"link_token": response.link_token}), 200
    except Exception as e:
        logging.error("Error generating Plaid link token: %s", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


# ---------------------------
# 7. Advanced AI-Driven Enhancements
# ---------------------------
# a. Smart Contract Execution (Simulated)
def execute_smart_contract(loan_agreement_id):
    """Simulate smart contract automation for a loan agreement.
       In a production system, this could trigger blockchain smart contracts."""
    agreement = LoanAgreement.query.get(loan_agreement_id)
    if agreement and agreement.status == "active":
        # Example: Auto-trigger repayment schedules and lock account details.
        agreement.status = "under_contract"
        db.session.commit()
        return {"contract_status": "executed", "loan_agreement_id": loan_agreement_id}
    return {"contract_status": "failed", "reason": "Invalid agreement or status."}

@app.route('/execute_contract/<int:loan_agreement_id>', methods=['POST'])
@jwt_required()
def execute_contract(loan_agreement_id):
    """Endpoint to execute a smart contract for a given loan agreement."""
    result = execute_smart_contract(loan_agreement_id)
    return jsonify(result), 200

# b. Real-Time Financial Health Score
def generate_financial_health_score(user_id):
    """Calculates a simple financial health score for a user based on transaction history."""
    transactions = Transaction.query.filter_by(user_id=user_id).all()
    if transactions:
        total = sum(t.amount for t in transactions)
        score = total / len(transactions)  # Simplified evaluation
    else:
        score = 100  # Default healthy score if no transactions are found
    return {"user_id": user_id, "financial_health_score": score}

@app.route('/financial_health/<int:user_id>', methods=['GET'])
@jwt_required()
def financial_health(user_id):
    """Endpoint to get a real-time financial health score for a user."""
    result = generate_financial_health_score(user_id)
    return jsonify(result), 200

# c. Multi-Currency Conversion for Global Lending
def get_exchange_rate(from_currency, to_currency):
    """Placeholder: Retrieve exchange rate from an external API.
       Replace with actual API integration (e.g., Open Exchange Rates)."""
    return 1.0  # For simplicity, return 1.0

def convert_currency(amount, from_currency, to_currency):
    """Converts an amount from one currency to another using live exchange rates."""
    exchange_rate = get_exchange_rate(from_currency, to_currency)
    return amount * exchange_rate

@app.route('/convert_currency', methods=['POST'])
@jwt_required()
def convert_currency_route():
    """Endpoint for converting currencies, enabling cross-border transactions."""
    data = request.json
    converted_amount = convert_currency(
        data.get('amount', 0),
        data.get('from_currency', 'USD'),
        data.get('to_currency', 'USD')
    )
    return jsonify({"converted_amount": converted_amount}), 200

# d. Secure Biometric Authentication (Placeholder)
@app.route('/biometric_auth', methods=['POST'])
def biometric_auth():
    """Endpoint placeholder for biometric authentication.
       Integrate with specialized biometric authentication services or SDKs."""
    data = request.json
    # Example: Verify fingerprint data, facial recognition, etc.
    return jsonify({"status": "authenticated", "message": "Biometric authentication successful"}), 200

# ---------------------------
# 8. Health Check & Error Handlers
# ---------------------------
@app.route('/health', methods=['GET'])
def health_check():
    """Simple endpoint to report API health."""
    return jsonify({"status": "healthy"}), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"message": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"message": "An internal error occurred"}), 500

# ---------------------------
# 9. App Initialization & Run
# ---------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Initializes all defined tables, including User, LoanAgreement, Transaction, etc.
    app.run(host='0.0.0.0', port=5000)
