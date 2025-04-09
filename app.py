from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, logging
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import csv
import pdfplumber
from bson import ObjectId
from fpdf import FPDF
from datetime import datetime
import requests
import plaid
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
import json

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
    linked_accounts_collection = db['linked_accounts'] # Ensure this collection exists
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    raise

# Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Plaid API Configuration
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')
PLAID_PRODUCTS = os.getenv('PLAID_PRODUCTS', 'auth')
PLAID_COUNTRY_CODES = os.getenv('PLAID_COUNTRY_CODES', 'US')
client = plaid.Client(client_id=PLAID_CLIENT_ID, secret=PLAID_SECRET, environment=PLAID_ENV)

# Treasury Prime API configuration
TREASURY_PRIME_ENV = os.getenv('TREASURY_PRIME_ENV', 'sandbox')
if TREASURY_PRIME_ENV == 'production':
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_PRODUCTION_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_PRODUCTION_API_URL')
else:
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_SANDBOX_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_SANDBOX_API_URL')

if TREASURY_PRIME_API_URL is None:
    print("Warning: TREASURY_PRIME_API_URL is not set in the environment variables.")

# Global account balance
global_account_balance = 848583.68  # Original balance
access_token = None # Initialize access_token globally
item_id = None # Initialize item_id globally

# User class for authentication (assuming you have a way to find users)
class User(UserMixin):
    def __init__(self, id, username=None):
        self.id = id
        self.username = username

    @staticmethod
    def find(user_identifier):
        # Replace this with your actual user lookup logic (e.g., from database)
        # if user_identifier == "some_user_id":
        #     return User("some_user_id", username="test_user")
        return User(user_identifier) # Placeholder

    @staticmethod
    def authenticate(username, password):
        # Example user lookup
        user_data = {"username": "test_user", "password": "test_password"}
        if username == user_data["username"] and password == user_data["password"]:
            return User("1", username=user_data["username"])
        return None

@login_manager.user_loader
def load_user(user_id):
    # Load the user from session
    return User(user_id)

# Calculate global balance
def calculate_global_balance():
    global global_account_balance
    account_data = accounts_collection.find()
    balance = sum(account.get('balance', 0) for account in account_data)
    return global_account_balance + balance

# Treasury Prime API integration
def verify_treasury_prime_account(account_id):
    headers = {
        'Authorization': f'Bearer {TREASURY_PRIME_API_KEY}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(f'{TREASURY_PRIME_API_URL}/accounts/{account_id}', headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error verifying Treasury Prime account: {e}")
        raise

# Routes
@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/account-info')
@login_required
def account_info():
    global global_account_balance
    user_balance = accounts_collection.find_one({"user_id": current_user.id}, {"balance": 1}) or {"balance": 0}
    user_balance = user_balance.get("balance")
    total_global_balance = calculate_global_balance()
    return render_template('account_info.html', account_balance=user_balance, global_balance=total_global_balance)

@app.route('/global_balance', methods=['GET'])
@login_required
def global_balance():
    try:
        balance = calculate_global_balance()
        return jsonify({"global_balance": balance}), 200
    except Exception as e:
        return jsonify({"message": "Error calculating global balance", "error": str(e)}), 500

@app.route('/upload-pdf', methods=['POST'])
@login_required
def upload_pdf():
    global global_account_balance
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        try:
            # Placeholder for PDF parsing logic
            # statements = parse_pdf(filename)
            # account_updates = correct_discrepancies(statements)
            # for update in account_updates:
            #     global_account_balance += float(update["amount"])

            return jsonify({"message": "PDF uploaded successfully (processing not yet implemented)"}), 200
        except Exception as e:
            return jsonify({"message": "Error processing file", "error": str(e)}), 500
    return jsonify({"message": "Invalid file format"}), 400

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "database": "connected" if mongo_client else "disconnected"}), 200

@app.route("/create_link_token", methods=['POST'])
@login_required
def create_link_token():
    # Get the client_user_id by searching for the current user
    user = User.find(current_user.id) # Assuming current_user.id is available
    client_user_id = user.id

    # Create a link_token for the given user
    request = LinkTokenCreateRequest(
        products=[Products("auth")],
        client_name="Plaid Test App",
        country_codes=[CountryCode('US')],
        redirect_uri='https://domainname.com/oauth-page.html', # Replace with your actual redirect URI
        language='en',
        webhook=os.getenv('PLAID_WEBHOOK_URL'), # Optional
        user=LinkTokenCreateRequestUser(
            client_user_id=client_user_id
        )
    )
    try:
        response = client.link_token_create(request)
        # Send the data to the client
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/exchange_public_token', methods=['POST'])
@login_required
def exchange_public_token():
    global access_token
    public_token = request.form.get('public_token') # Assuming public_token is sent as form data
    if not public_token:
        return jsonify({'error': 'Missing public_token'}), 400
    request = ItemPublicTokenExchangeRequest(
        public_token=public_token
    )
    try:
        response = client.item_public_token_exchange(request)
        access_token = response['access_token']
        item_id = response['item_id']

        # Store the access token and item ID in your database
        linked_accounts_collection.update_one(
            {'user_id': current_user.id, 'plaid_item_id': item_id},
            {'$set': {
                'plaid_access_token': access_token,
                'link_date': datetime.utcnow()
            }},
            upsert=True
        )

        return jsonify({'public_token_exchange': 'complete'}), 200
    except plaid.ApiException as e:
        response_json = json.loads(e.body)
        return jsonify({'error': {'status_code': e.status, 'display_message':
                                    response_json['error_message'], 'error_code': response_json['error_code'], 'error_type': response_json['error_type']}}), e.status

# Retrieve an Item's accounts
@app.route('/accounts', methods=['GET'])
@login_required
def get_accounts():
    linked_account = linked_accounts_collection.find_one({'user_id': current_user.id})
    if not linked_account or not linked_account.get('plaid_access_token'):
        return jsonify({'error': 'No linked account found for this user'}), 404

    access_token = linked_account['plaid_access_token']

    try:
        request = AccountsGetRequest(
            access_token=access_token
        )
        accounts_response = client.accounts_get(request)
        return jsonify(accounts_response.to_dict()), 200
    except plaid.ApiException as e:
        response_json = json.loads(e.body)
        return jsonify({'error': {'status_code': e.status, 'display_message':
                                    response_json['error_message'], 'error_code': response_json['error_code'], 'error_type': response_json['error_type']}}), e.status

# Placeholder for supporting functions (parse_pdf, parse_page, correct_discrepancies, etc.)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
