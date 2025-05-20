# app/routes.py

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User, LoanAgreement, Transaction
from app.utils import analyze_loan_agreement, detect_fraudulent_transaction, execute_smart_contract
from app.services.plaid_api import generate_link_token  # Modularized Plaid integration

bp = Blueprint('api', __name__)

# ---------------------------
# 1. Health Check Endpoint
# ---------------------------
@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# ---------------------------
# 2. User Authentication & Registration
# ---------------------------
@bp.route('/api/register', methods=['POST'])
def register():
    """Registers a new user with a hashed password."""
    data = request.json
    username, password = data.get("username"), data.get("password")

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "User already exists"}), 400

    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    return jsonify({"msg": "User created"}), 201

@bp.route('/api/login', methods=['POST'])
def login():
    """Authenticates user and returns JWT token."""
    data = request.get_json()
    username, password = data.get('username'), data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200
    return jsonify({"msg": "Invalid credentials"}), 401

# ---------------------------
# 3. Loan Agreement Management & AI Compliance
# ---------------------------
@bp.route('/review_agreement', methods=['POST'])
@jwt_required()
def review_agreement():
    """AI scans and verifies loan agreements."""
    data = request.json
    borrower_id, agreement_text = data.get('borrower_id'), data.get('terms', '')

    result = analyze_loan_agreement(agreement_text)
    borrower_agreements = LoanAgreement.query.filter_by(borrower_id=borrower_id).all()

    if result["status"] == "flagged":
        for agreement in borrower_agreements:
            agreement.violation_count += 1
            if agreement.violation_count >= 3:  # Lock account after 3 violations
                agreement.locked = True
        db.session.commit()

    return jsonify(result), 200

@bp.route('/compliance_report', methods=['GET'])
@jwt_required()
def compliance_report():
    """Generates a compliance report based on flagged loan agreements."""
    agreements = LoanAgreement.query.all()
    flagged = [ag for ag in agreements if ag.ai_flagged]
    return jsonify({"violations": [ag.id for ag in flagged] if flagged else "compliant"}), 200

# ---------------------------
# 4. Fraud Detection & Financial Security
# ---------------------------
@bp.route('/validate_transaction', methods=['POST'])
@jwt_required()
def validate_transaction():
    """Flags fraudulent transactions and auto-locks borrower accounts on severe fraud detection."""
    data = request.json
    borrower_id, description, amount = data.get('user_id'), data.get('description', ''), data.get('amount', 0)

    if detect_fraudulent_transaction(description, amount):
        borrower_agreements = LoanAgreement.query.filter_by(borrower_id=borrower_id).all()
        for agreement in borrower_agreements:
            agreement.locked = True
        db.session.commit()
        return jsonify({"status": "locked", "message": "Transaction blocked due to fraud."}), 403

    return jsonify({"fraudulent": False}), 200

# ---------------------------
# 5. Smart Contract Execution
# ---------------------------
@bp.route('/execute_contract/<int:loan_agreement_id>', methods=['POST'])
@jwt_required()
def execute_contract(loan_agreement_id):
    """Endpoint to execute a smart contract for a loan agreement."""
    return jsonify(execute_smart_contract(loan_agreement_id)), 200

# ---------------------------
# 6. Fintech API Integration (Plaid)
# ---------------------------
@bp.route('/generate_link_token', methods=['GET'])
@jwt_required()
def generate_link():
    """Generates a Plaid Link token for banking integration."""
    return jsonify({"link_token": generate_link_token()}), 200

# ---------------------------
# 7. Miscellaneous Enhancements
# ---------------------------
@bp.route('/biometric_auth', methods=['POST'])
def biometric_auth():
    """Placeholder for biometric authentication."""
    return jsonify({"status": "authenticated", "message": "Biometric authentication successful"}), 200
