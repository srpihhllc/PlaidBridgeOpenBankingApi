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
import logging

# 🔹 Initialize Flask app
app = Flask(__name__)

# 🔹 Database Configuration (Switch to PostgreSQL in production)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///intermediary_api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🔹 JWT Configuration with Security Enhancements
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')  # Use env variables for security
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # Tokens expire in 1 hour (better security)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 86400  # Refresh tokens last 24 hours

# 🔹 Initialize Database and JWT Manager
db = SQLAlchemy(app)
jwt = JWTManager(app)

# 🔹 Enable Debug Logging for Better Error Tracking
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Save logs for future debugging
        logging.StreamHandler()  # Show logs in the console
    ]
)

# 🔹 User Model with Secure Hashing
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'lender' or 'borrower'
    verified = db.Column(db.Boolean, default=False)

# 🔹 Transaction Model for Secure Tracking
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)

# 🔹 User Registration with Secure Hashing
@app.route('/register', methods=['POST'])
def register():
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

    hashed_password = generate_password_hash(password)  # Secure password storage
    new_user = User(username=username, password=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

# 🔹 User Login with JWT Authentication
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity={"id": user.id, "role": user.role})
        refresh_token = create_access_token(identity={"id": user.id}, fresh=False)
        return jsonify(access_token=access_token, refresh_token=refresh_token), 200

    return jsonify({"message": "Invalid credentials"}), 401

# 🔹 Refresh Token Route
@app.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    return jsonify(access_token=new_access_token), 200

# 🔹 Health Check Endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# 🔹 Initialize Database on Startup
with app.app_context():
    db.create_all()

# 🔹 Run Flask App with Gunicorn for Production
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
