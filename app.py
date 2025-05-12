# --------------------------------------------
# Enhanced App for PlaidBridge Open Banking API
# --------------------------------------------

from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from limits.storage import RedisStorage  # ✅ Correct
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from celery import Celery
from marshmallow import Schema, fields, validate
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import os
import requests
import pdfplumber
from fpdf import FPDF
import pymongo
from dotenv import load_dotenv
from flask_prometheus_metrics import register_metrics
import gunicorn


# --------------------------------------------
# Load Environment Variables
# --------------------------------------------
load_dotenv()
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')

# --------------------------------------------
# Plaid Client Configuration
# --------------------------------------------
from plaid.api.plaid_api import PlaidApi
from plaid import ApiClient, Configuration
from plaid.model.link_token_create_request import LinkTokenCreateRequest

configuration = Configuration(
    host=f"https://{PLAID_ENV}.plaid.com",
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET}
)
api_client = ApiClient(configuration)
plaid_client = PlaidApi(api_client)

def create_link_token():
    """Generates a Plaid Link token for initializing Plaid Link."""
    request = LinkTokenCreateRequest(
        client_name="PlaidBridge Open Banking API",
        language="en",
        country_codes=["US"],
        user={"client_user_id": "unique-user-id"},
        products=["auth", "transactions"]
    )
    response = plaid_client.link_token_create(request)
    return response["link_token"]

# --------------------------------------------
# Flask App Initialization
# --------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://yourtrusteddomain.com"}})  # Restrict to trusted domains
register_metrics(app, app_version="v1.0.0", app_config="production")  # Prometheus metrics

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 86400

# Initialize Database, JWT, and Limiter
db = SQLAlchemy(app)
jwt = JWTManager(app)
limiter = Limiter(get_remote_address, app=app, storage=RedisStorage("redis://localhost:6379"))

# Celery Configuration
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# --------------------------------------------
# Models
# --------------------------------------------

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

# --------------------------------------------
# Input Validation Schemas
# --------------------------------------------

class RegisterSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3))
    password = fields.String(required=True, validate=validate.Length(min=6))
    role = fields.String(required=True, validate=validate.OneOf(["lender", "borrower"]))

# --------------------------------------------
# Routes
# --------------------------------------------

@app.route('/')
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')

@app.route('/register', methods=['POST'])
@limiter.limit("10 per minute")
def register():
    """Register a new user."""
    schema = RegisterSchema()
    errors = schema.validate(request.json)
    if errors:
        return jsonify(errors), 400

    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"message": "Resource not found"}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"message": "An internal error occurred"}), 500

# --------------------------------------------
# App Initialization and Run
# --------------------------------------------

if __name__ == '__main__':  # ✅ Remove extra space before 'if'
    with app.app_context():
        db.create_all()  # Initializes DB tables
    app.run(host='0.0.0.0', port=5000)  # Use Flask's built-in server for local testing



