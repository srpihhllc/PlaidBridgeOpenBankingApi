
from flask import Flask, jsonify, request, redirect, url_for
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
from plaid.model.link_token_account_filters import LinkTokenAccountFilters
from plaid.model.depository_filter import DepositoryFilter
from plaid.model.depository_account_subtypes import DepositoryAccountSubtypes
from plaid.model.credit_filter import CreditFilter
from plaid.model.credit_account_subtypes import CreditAccountSubtypes
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.auth_get_request import AuthGetRequest # Import AuthGetRequest

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# Logging setup
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client_mongo = MongoClient(MONGO_URI)
db = client_mongo['open_banking_api']
accounts_collection = db['accounts']
linked_accounts_collection = db['linked_accounts']

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # If you had a login route

class User(UserMixin):
    def __init__(self, id):
        self.id = id

    @staticmethod
    def find(user_id):
        user_data = accounts_collection.find_one({'user_id': user_id})
        if user_data:
            return User(user_data['user_id'])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.find(user_id)

# Plaid API client setup
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')  # Default to sandbox
client = plaid.Client(client_id=PLAID_CLIENT_ID, secret=PLAID_SECRET, environment=PLAID_ENV)

# Treasury Prime API configuration
TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_API_URL')
TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_API_KEY')

# Global account balance (for internal lending)
global_account_balance = 1000000.00  # Example initial balance

# Placeholder for access token and item ID (will be stored per user in DB)
# access_token = None
# item_id = None

def calculate_global_balance():
    total_balance = global_account_balance
    # You might want to aggregate balances from user accounts in MongoDB here in the future
    for account in accounts_collection.find():
        if 'balance' in account and isinstance(account['balance'], (int, float)):
            total_balance += account['balance']
    return total_balance

def verify_treasury_prime_account(account_id):
    if not TREASURY_PRIME_API_URL or not TREASURY_PRIME_API_KEY:
        logger.warning("Treasury Prime API URL or Key not configured.")
        return None
    url = f"{TREASURY_PRIME_API_URL}/accounts/{account_id}"
    headers = {
        'Authorization': f'Bearer {TREASURY_PRIME_API_KEY}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error verifying Treasury Prime account {account_id}: {e}")
        return None

# --- New function to Get Account and Routing Numbers using Plaid Auth ---
def get_plaid_auth_details(access_token):
    request = AuthGetRequest(access_token=access_token)
    try:
        response = client.auth_get(request)
        accounts = response.to_dict().get('accounts', [])
        numbers = response.to_dict().get('numbers', [])
        return accounts, numbers
    except plaid.ApiException as e:
        logger.error(f"Error getting Plaid Auth details: {e}")
        return None, None

@app.route("/")
@login_required
def index():
    user = User.find(current_user.id)
    global_balance = calculate_global_balance()
    return f"Hello, {user.id}! Global Balance: {global_balance}"

@app.route("/account-info")
@login_required
def account_info():
    user = User.find(current_user.id)
    global_balance = calculate_global_balance()
    return jsonify({'user_id': user.id, 'global_balance': global_balance})

@app.route("/global_balance")
@login_required
def get_global_balance():
    global_balance = calculate_global_balance()
    return jsonify({'global_balance': global_balance})

@app.route("/upload-pdf", methods=['POST'])
@login_required
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.endswith('.pdf'):
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        # Placeholder for PDF processing logic
        return jsonify({'message': 'PDF uploaded successfully', 'filename': filename})
    return jsonify({'error': 'Invalid file format. Only PDF allowed'}), 400

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"})

@app.route("/create_link_token", methods=['POST'])
@login_required
def create_link_token():
    user = User.find(current_user.id) # Assuming current_user.id is available
    client_user_id = user.id
    logger.info(f"User {current_user.id} requesting Plaid link token.")
    request_obj = LinkTokenCreateRequest(
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
        response = client.link_token_create(request_obj)
        logger.info(f"Plaid link token created for user {current_user.id}.")
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Error creating Plaid link token for user {current_user.id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/exchange_public_token", methods=['POST'])
@login_required
def exchange_public_token():
    public_token = request.json.get('public_token')
    if not public_token:
        return jsonify({'error': 'Missing public_token'}), 400

    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = client.item_public_token_exchange(exchange_request)
        access_token = exchange_response.to_dict()['access_token']
        item_id = exchange_response.to_dict()['item_id']

        # Retrieve Auth details
        accounts, numbers = get_plaid_auth_details(access_token)

        ach_details = []
        if numbers:
            for number in numbers:
                if number.get('ach'):
                    ach_details.append(number.get('ach'))

        # Store access_token, item_id, and ACH details in MongoDB
        linked_accounts_collection.update_one(
            {'user_id': current_user.id},
            {'$set': {'plaid_access_token': access_token, 'plaid_item_id': item_id, 'ach_details': ach_details}},
            upsert=True
        )

        logger.info(f"Plaid exchange successful for user {current_user.id}, item ID: {item_id}")
        return jsonify({'access_token': access_token, 'item_id': item_id, 'ach_details': ach_details})
    except plaid.ApiException as e:
        logger.error(f"Error exchanging public token for user {current_user.id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/accounts", methods=['GET'])
@login_required
def get_accounts():
    linked_account = linked_accounts_collection.find_one({'user_id': current_user.id})
    if not linked_account or 'plaid_access_token' not in linked_account:
        return jsonify({'error': 'No linked account found'}), 400

    access_token = linked_account['plaid_access_token']
    try:
        accounts_request = AccountsGetRequest(access_token=access_token)
        accounts_response = client.accounts_get(accounts_request)
        accounts = accounts_response.to_dict()['accounts']
        return jsonify(accounts)
    except plaid.ApiException as e:
        logger.error(f"Error retrieving Plaid accounts for user {current_user.id}: {e}")
        return jsonify({'error': str(e)}), 500

# Placeholder for supporting functions (e.g., PDF parsing, data correction, etc.)

if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
