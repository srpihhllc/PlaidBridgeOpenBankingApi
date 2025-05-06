from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intermediary_api.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'lender' or 'borrower'
    verified = db.Column(db.Boolean, default=False)
    routing_number = db.Column(db.String(20), nullable=True)
    account_number = db.Column(db.String(20), nullable=True)
    ssn = db.Column(db.String(11), nullable=True)
    company_name = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(200), nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)

# Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')  # 'lender' or 'borrower'

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
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity={"id": user.id, "role": user.role})
        return jsonify(access_token=access_token), 200

    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/link-account', methods=['POST'])
@jwt_required()
def link_account():
    current_user = get_jwt_identity()
    data = request.json

    if current_user['role'] == 'borrower':
        # Borrower account linking logic
        routing_number = data.get('routing_number')
        account_number = data.get('account_number')
        ssn = data.get('ssn')

        if not routing_number or not account_number or not ssn:
            return jsonify({"message": "Missing required fields"}), 400

        user = User.query.get(current_user['id'])
        user.routing_number = routing_number
        user.account_number = account_number
        user.ssn = ssn
        db.session.commit()

        return jsonify({"message": "Borrower account linked successfully"}), 200

    elif current_user['role'] == 'lender':
        # Lender account linking logic
        company_name = data.get('company_name')
        address = data.get('address')
        routing_number = data.get('routing_number')
        account_number = data.get('account_number')

        if not company_name or not address or not routing_number or not account_number:
            return jsonify({"message": "Missing required fields"}), 400

        user = User.query.get(current_user['id'])
        user.company_name = company_name
        user.address = address
        user.routing_number = routing_number
        user.account_number = account_number
        user.verified = True  # Lenders must be verified
        db.session.commit()

        return jsonify({"message": "Lender account linked and verified successfully"}), 200

    return jsonify({"message": "Invalid role"}), 403

@app.route('/upload-statement', methods=['POST'])
@jwt_required()
def upload_statement():
    """Handles upload and processing of bank statements."""
    file = request.files.get('file')
    if not file:
        return jsonify({"message": "No file uploaded"}), 400

    # Save and process the file (CSV or PDF handling logic will be added later)
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    # Placeholder: Simulate processing
    return jsonify({"message": "Statement uploaded successfully", "file": file.filename}), 200

# Health Check
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# Initialize the database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
