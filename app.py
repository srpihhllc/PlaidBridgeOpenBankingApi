# --------------------------------------------
# Enhanced App for PlaidBridge Open Banking API
# (Updated per AppVision – No Redis, Extra Functionalities)
# --------------------------------------------

from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# Removed: from limits.storage import RedisStorage (Redis removed)
from flask_cors import CORS
# Removed Celery since you no longer need a Redis broker:
# from celery import Celery
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
    request_body = LinkTokenCreateRequest(
        client_name="PlaidBridge Open Banking API",
        language="en",
        country_codes=["US"],
        user={"client_user_id": "unique-user-id"},
        products=["auth", "transactions"]
    )
    response = plaid_client.link_token_create(request_body)
    return response["link_token"]

# --------------------------------------------
# Flask App Initialization
# --------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://yourtrusteddomain.com"}})
register_metrics(app, app_version="v1.0.0", app_config="production")

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 86400

# Initialize Database, JWT
db = SQLAlchemy(app)
jwt = JWTManager(app)

# --------------------------------------------
# Rate Limiting (Redis removed – using default in-memory storage)
# --------------------------------------------
limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

# --------------------------------------------
# Logging Configuration
# --------------------------------------------
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

# New Model for To-Do List Functionality
class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --------------------------------------------
# Input Validation Schemas
# --------------------------------------------

class RegisterSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3))
    password = fields.String(required=True, validate=validate.Length(min=6))
    role = fields.String(required=True, validate=validate.OneOf(["lender", "borrower"]))

class TodoSchema(Schema):
    content = fields.String(required=True, validate=validate.Length(min=1))
    completed = fields.Boolean()

# --------------------------------------------
# Helper Functions
# --------------------------------------------

def calculate_global_balance():
    """Aggregates the balance from all transactions."""
    balance = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0.0
    return balance

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

@app.route('/login', methods=['POST'])
def login():
    """User login."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"message": "Incorrect username or password"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({"access_token": access_token}), 200

# --------------------------------------------
# To-Do List Endpoints (Task Management)
# --------------------------------------------

@app.route('/todos', methods=['GET'])
@jwt_required()
def get_todos():
    """Fetch all to-dos for the logged-in user."""
    user_id = get_jwt_identity()
    todos = Todo.query.filter_by(user_id=user_id).all()
    todo_schema = TodoSchema(many=True)
    return jsonify(todo_schema.dump(todos)), 200

@app.route('/todos', methods=['POST'])
@jwt_required()
def add_todo():
    """Add a new to-do item for the logged-in user."""
    user_id = get_jwt_identity()
    todo_schema = TodoSchema()
    errors = todo_schema.validate(request.json)
    if errors:
        return jsonify(errors), 400

    data = request.json
    new_todo = Todo(content=data.get('content'),
                    completed=data.get('completed', False),
                    user_id=user_id)
    db.session.add(new_todo)
    db.session.commit()
    return jsonify(todo_schema.dump(new_todo)), 201

@app.route('/todos/<int:todo_id>', methods=['PUT'])
@jwt_required()
def update_todo(todo_id):
    """Update an existing to-do item."""
    user_id = get_jwt_identity()
    todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
    if not todo:
        return jsonify({"message": "Todo not found"}), 404

    data = request.json
    if 'content' in data:
        todo.content = data['content']
    if 'completed' in data:
        todo.completed = data['completed']
    db.session.commit()
    todo_schema = TodoSchema()
    return jsonify(todo_schema.dump(todo)), 200

@app.route('/todos/<int:todo_id>', methods=['DELETE'])
@jwt_required()
def delete_todo(todo_id):
    """Delete a to-do item."""
    user_id = get_jwt_identity()
    todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
    if not todo:
        return jsonify({"message": "Todo not found"}), 404

    db.session.delete(todo)
    db.session.commit()
    return jsonify({"message": "Todo deleted"}), 200

# --------------------------------------------
# Global Account Balance Tracking Endpoint
# --------------------------------------------

@app.route('/global_balance', methods=['GET'])
@jwt_required()
def global_balance():
    """Return the aggregated global balance from all transactions."""
    balance = calculate_global_balance()
    return jsonify({"global_balance": balance}), 200

# --------------------------------------------
# PDF Statement Processing & Transaction Verification
# --------------------------------------------

@app.route('/upload_statement', methods=['POST'])
@jwt_required()
def upload_statement():
    """
    Receive a bank statement PDF, process it using pdfplumber, and extract relevant text.
    (Further AI validation and corrections can be added here.)
    """
    if 'file' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400

    try:
        with pdfplumber.open(file) as pdf:
            first_page = pdf.pages[0]
            extracted_text = first_page.extract_text()
    except Exception as e:
        return jsonify({'message': f'Error processing PDF: {str(e)}'}), 500

    return jsonify({'message': 'Statement processed successfully', 'extracted_text': extracted_text}), 200

# --------------------------------------------
# Health Check & Error Handlers
# --------------------------------------------

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Initializes DB tables
    app.run(host='0.0.0.0', port=5000)  # Use Flask's built-in server for local testing
