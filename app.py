from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import os
import logging
from plaid import Client as PlaidClient

# 🔹 Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# 🔹 Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')  # Use PostgreSQL in production
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🔹 JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')  # Use env variables for production
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # Tokens expire in 1 hour
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 86400  # Refresh tokens last 24 hours

# 🔹 Initialize Database and JWT Manager
db = SQLAlchemy(app)
jwt = JWTManager(app)

# 🔹 Logging Configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# 🔹 Plaid API Client Configuration
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')  # Default to sandbox for testing

plaid_client = PlaidClient(client_id=PLAID_CLIENT_ID, secret=PLAID_SECRET, environment=PLAID_ENV)

# 🔹 Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'lender' or 'borrower'
    verified = db.Column(db.Boolean, default=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    ai_verified = db.Column(db.Boolean, default=False)

class LoanAgreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    terms = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="active")  # 'active', 'completed', 'defaulted'
    ai_flagged = db.Column(db.Boolean, default=False)

# 🔹 Routes
@app.route('/')
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')

@app.route('/register', methods=['POST'])
def register():
    """Register a new user (lender or borrower)."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')

    if not username or not password or not role:
        return jsonify({"message": "Missing required fields"}), 400

    if role not in ['lender', 'borrower']:
        return jsonify({"message": "Invalid role. Must be 'lender' or 'borrower'"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    """Log in a user and return access and refresh tokens."""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity={"id": user.id, "role": user.role})
        refresh_token = create_access_token(identity={"id": user.id}, fresh=False)
        return jsonify(access_token=access_token, refresh_token=refresh_token), 200

    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    """Generate a new access token using a refresh token."""
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    return jsonify(access_token=new_access_token), 200

@app.route('/link_account', methods=['POST'])
@jwt_required()
def link_account():
    """Link a user account using Plaid."""
    user_identity = get_jwt_identity()
    data = request.json
    public_token = data.get('public_token')

    if not public_token:
        return jsonify({"message": "Missing public token"}), 400

    exchange_response = plaid_client.Item.public_token.exchange(public_token)
    access_token = exchange_response['access_token']
    item_id = exchange_response['item_id']

    # Store access_token securely (not implemented here for brevity)
    return jsonify({"message": "Account linked successfully", "item_id": item_id}), 200

@app.route('/analyze_loan', methods=['POST'])
@jwt_required()
def analyze_loan():
    """Analyze loan agreements for unethical practices."""
    data = request.json
    terms = data.get('terms')

    if not terms:
        return jsonify({"message": "Missing loan terms"}), 400

    # Mock AI analysis
    unethical = "high penalty" in terms.lower()  # Example flagging rule

    if unethical:
        return jsonify({"message": "Loan flagged for unethical practices"}), 400

    return jsonify({"message": "Loan terms are ethical"}), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

# 🔹 Initialize Database on Startup
with app.app_context():
    db.create_all()

# 🔹 Run Flask App
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
