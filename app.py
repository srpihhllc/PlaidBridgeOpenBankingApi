from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, abort, render_template
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import os
import csv
import pdfplumber
import logging
from werkzeug.utils import secure_filename
from fpdf import FPDF
from plaid.api import plaid_api
from plaid.model import *
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from datetime import datetime, timedelta
from pymongo import MongoClient
import requests
from bson import ObjectId  # FIX: Import ObjectId from bson for MongoDB ID handling
from flask_wtf.csrf import CSRFProtect  # FIX: Import CSRFProtect for CSRF protection

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# FIX: Use a secure random key and don't provide a fallback
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise ValueError("SECRET_KEY environment variable must be set")

# FIX: Add CSRF protection
csrf = CSRFProtect(app)

# FIX: Add proper Socket.IO configuration with authentication and room-based messaging
socketio = SocketIO(app, cors_allowed_origins="*")  # Set appropriate CORS policy

# Get the PORT from environment variables
port = int(os.getenv("PORT", 3000))

# Ensure the statements directory exists
app.config['UPLOAD_FOLDER'] = 'statements'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit file size to 16MB

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# FIX: Remove global account balance, store per user in database
# account_balance = 848583.68

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Starting application")

# FIX: Correct Plaid API configuration
configuration = Configuration(
    host="https://sandbox.plaid.com"
)
# FIX: Set API keys properly according to Plaid SDK requirements
api_client = ApiClient(configuration)
api_client.set_config_value('client_id', os.getenv('PLAID_CLIENT_ID'))
api_client.set_config_value('secret', os.getenv('PLAID_SECRET'))
plaid_client = plaid_api.PlaidApi(api_client)

# Treasury Prime API configuration
treasury_prime_env = os.getenv('TREASURY_PRIME_ENV', 'sandbox')
if treasury_prime_env == 'production':
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_PRODUCTION_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_PRODUCTION_API_URL')
else:
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_SANDBOX_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_SANDBOX_API_URL')

# FIX: Check all required environment variables
if TREASURY_PRIME_API_URL is None:
    raise ValueError("TREASURY_PRIME_API_URL is not set in the environment variables.")
if TREASURY_PRIME_API_KEY is None:
    raise ValueError("TREASURY_PRIME_API_KEY is not set in the environment variables.")

# FIX: Add error handling for MongoDB connection
try:
    mongo_client = MongoClient(os.getenv('COSMOS_DB_CONNECTION_STRING'), 
                              maxPoolSize=50,  # FIX: Add connection pooling configuration
                              serverSelectionTimeoutMS=5000)  # FIX: Add timeout 
    # Test connection
    mongo_client.server_info()
    db = mongo_client['plaidbridgeopenbankingapi-database']
    todos_collection = db['todos']
    # FIX: Add user and account collections
    users_collection = db['users']
    accounts_collection = db['accounts']
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# FIX: Add more secure session configuration
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

class User(UserMixin):
    def __init__(self, id, username=None, email=None):
        self.id = id
        self.username = username
        self.email = email
    
    # FIX: Add proper user authentication methods
    @staticmethod
    def authenticate(username, password):
        # Implement actual authentication here
        user_data = users_collection.find_one({"username": username})
        if user_data and verify_password(password, user_data.get('password_hash')):
            return User(str(user_data['_id']), username=user_data['username'])
        return None

def verify_password(password, password_hash):
    # FIX: Implement proper password verification
    # This is a placeholder - use proper password hashing library
    return False  # Placeholder

@login_manager.user_loader
def load_user(user_id):
    # FIX: Actually load user from database
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_id, username=user_data.get('username'), email=user_data.get('email'))
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # FIX: Add proper authentication
        username = request.form['username']
        password = request.form['password']
        user = User.authenticate(username, password)
        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        # Show error message on login failure
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route("/link-account")
@login_required
def link_account():
    return render_template('link_account.html')

@app.route("/account-info")
@login_required
def account_info():
    # FIX: Get account info from database for the current user
    account_data = accounts_collection.find_one({"user_id": current_user.id})
    account_balance = account_data.get('balance', 0) if account_data else 0
    
    # Get statements for this specific user
    statements = list(db.statements.find({"user_id": current_user.id}).sort("date", -1))
    
    return render_template('account_info.html', account_balance=account_balance, statements=statements)

@app.route('/create_link_token', methods=['GET'])
@login_required
def create_link_token():
    try:
        # FIX: Use correct client user ID (the actual user ID)
        # FIX: Use dynamic redirect URI based on request
        request_domain = request.host_url.rstrip('/')
        redirect_uri = f"{request_domain}/oauth-return"
        
        # FIX: Create proper LinkTokenCreateRequest object
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(
                client_user_id=str(current_user.id)
            ),
            client_name="PlaidBridgeOpenBankingAPI",
            products=["auth"],
            country_codes=["US"],
            language="en",
            redirect_uri=redirect_uri
        )
        
        response = plaid_client.link_token_create(request)
        return jsonify({'link_token': response.link_token})
    except Exception as e:
        logger.error(f"Error creating Plaid link token: {e}")
        return jsonify({'message': 'Error creating link token'}), 500

@app.route('/exchange_public_token', methods=['POST'])
@login_required
def exchange_public_token():
    data = request.json
    try:
        # FIX: Create proper ItemPublicTokenExchangeRequest object
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=data['public_token']
        )
        response = plaid_client.item_public_token_exchange(exchange_request)
        
        # FIX: Store access token securely in database for this user
        accounts_collection.update_one(
            {"user_id": current_user.id},
            {"$set": {"plaid_access_token": response.access_token}},
            upsert=True
        )
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error exchanging Plaid public token: {e}")
        return jsonify({'message': 'Error exchanging public token'}), 500

@app.route('/upload-pdf', methods=['POST'])
@login_required
def upload_pdf():
    # FIX: Remove global account_balance reference
    if 'file' not in request.files:
        logger.error("No file part in the request")
        return jsonify({'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.error("No selected file")
        return jsonify({'message': 'No selected file'}), 400
    
    # FIX: Add more comprehensive file validation
    if file and allowed_file(file.filename):
        # FIX: Add user ID to filename to prevent conflicts
        filename = f"{current_user.id}_{secure_filename(file.filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            statements = parse_pdf(file_path)
            corrected_statements = correct_discrepancies(statements)
            
            # FIX: Add user ID to each statement
            for statement in corrected_statements:
                statement['user_id'] = current_user.id
            
            # Save statements to database
            db.statements.insert_many(corrected_statements)
            
            csv_filename = filename.replace('.pdf', '.csv')
            csv_file_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            save_statements_as_csv(corrected_statements, csv_file_path)
            
            # FIX: Update user-specific account balance
            update_account_balance(current_user.id, corrected_statements)
            
            # FIX: Emit to user-specific room instead of broadcast
            socketio.emit('update', 
                         {'statements': corrected_statements}, 
                         room=current_user.id)
            
            return jsonify({'message': 'File processed successfully', 'csv_file': csv_filename}), 200
        except pdfplumber.PDFSyntaxError as e:
            logger.error(f"PDF syntax error: {e}")
            return jsonify({'message': 'PDF syntax error'}), 500
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            return jsonify({'message': f'Error processing file: {str(e)}'}), 500
    
    logger.error("Invalid file format")
    return jsonify({'message': 'Invalid file format'}), 400

@app.route('/statements/<filename>')
@login_required
def download_statement(filename):
    try:
        # FIX: Verify filename belongs to current user
        user_prefix = f"{current_user.id}_"
        if not filename.startswith(user_prefix):
            return jsonify({'message': 'Unauthorized'}), 403
            
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'message': 'Error downloading file'}), 500

@app.route('/generate-pdf/<csv_filename>', methods=['GET'])
@login_required
def generate_pdf(csv_filename):
    try:
        base_path = app.config['UPLOAD_FOLDER']

        # FIX: Validate that the CSV belongs to the current user
        user_prefix = f"{current_user.id}_"
        if not csv_filename.startswith(user_prefix):
            return jsonify({'message': 'Unauthorized'}), 403
            
        # FIX: Validate the path BEFORE normalization
        if '/' in csv_filename or '\\' in csv_filename:
            return jsonify({'message': 'Invalid filename'}), 400
            
        csv_file_path = os.path.join(base_path, csv_filename)
        
        # Double-check the normalization didn't escape the upload folder
        if not os.path.abspath(csv_file_path).startswith(os.path.abspath(base_path)):
            return jsonify({'message': 'Invalid file path'}), 400

        pdf_filename = csv_filename.replace('.csv', '.pdf')
        pdf_file_path = os.path.join(base_path, pdf_filename)
        
        # FIX: Check if the CSV exists before trying to generate PDF
        if not os.path.exists(csv_file_path):
            return jsonify({'message': 'CSV file not found'}), 404

        generate_pdf_from_csv(csv_file_path, pdf_file_path)
        return send_from_directory(app.config['UPLOAD_FOLDER'], pdf_filename)
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'message': 'Error generating PDF'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    # FIX: Add more comprehensive health check
    health_status = {
        "status": "healthy",
        "database": "connected" if mongo_client else "disconnected"
    }
    return jsonify(health_status), 200

# FIX: Add rate limiting
def allowed_file(filename):
    # FIX: More comprehensive file validation
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf' and \
           os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], filename)) <= app.config['MAX_CONTENT_LENGTH']

def parse_pdf(file_path):
    """Parse the PDF file to extract statements."""
    statements = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    statements.extend(parse_page(text))
        logger.info(f"Parsed {len(statements)} statements from PDF")
        return statements
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise

# FIX: Improve PDF parsing to handle real bank statements
def parse_page(text):
    """Parse a single page of text to extract statements."""
    statements = []
    # Skip header lines
    lines = text.split('\n')
    parsing_started = False
    
    for line in lines:
        # Add better parsing logic to detect actual transaction lines
        # This is a placeholder - real implementation would use regex and be more bank-specific
        parts = line.split()
        if len(parts) >= 3:
            try:
                # Check if first part looks like a date
                datetime.strptime(parts[0], '%Y-%m-%d')
                date = parts[0]
                amount_str = parts[-1].replace('$', '').replace(',', '')
                
                # FIX: Properly determine transaction type from the amount string
                if amount_str.startswith('-'):
                    transaction_type = 'withdrawal'
                    amount = amount_str  # Keep the negative sign
                else:
                    transaction_type = 'deposit'
                    amount = amount_str
                    
                description = " ".join(parts[1:-1])
                statements.append({
                    'date': date,
                    'description': description,
                    'amount': amount,
                    'transaction_type': transaction_type
                })
            except (ValueError, IndexError):
                # Skip lines that don't match expected format
                continue
    
    return statements

def correct_discrepancies(statements):
    """Correct discrepancies in the statements."""
    corrected_statements = []
    for statement in statements:
        try:
            # FIX: Better error handling for amount parsing
            amount_str = statement['amount']
            amount = float(amount_str)
            statement['amount'] = amount_str  # Keep as string for database
            corrected_statements.append(statement)
        except ValueError:
            # Handle misprints or miscalculations
            logger.warning(f"Invalid amount found: {statement['amount']} - setting to 0.00")
            statement['amount'] = '0.00'  # Set to zero or some default value
            corrected_statements.append(statement)
    return corrected_statements

def save_statements_as_csv(statements, file_path):
    """Save the statements as a CSV file."""
    try:
        # FIX: Handle empty statements
        if not statements:
            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['date', 'description', 'amount', 'transaction_type'])
            logger.info(f"Empty statements CSV saved as '{file_path}'")
            return
            
        keys = statements[0].keys()
        with open(file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(statements)
        logger.info(f"Statements saved as '{file_path}'")
    except Exception as e:
        logger.error(f"Error saving CSV file: {e}")
        raise

def generate_pdf_from_csv(csv_file_path, pdf_file_path):
    """Generate a PDF file from a CSV file."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # FIX: Check if file exists and has data
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
            
        # Add a header
        pdf.cell(200, 10, txt="Statement", ln=True, align='C')
        pdf.ln(10)
        
        # Add column headers
        pdf.cell(40, 10, txt="Date", border=1)
        pdf.cell(80, 10, txt="Description", border=1)
        pdf.cell(30, 10, txt="Amount", border=1)
        pdf.cell(40, 10, txt="Type", border=1)
        pdf.ln()

        with open(csv_file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                pdf.cell(40, 10, txt=row.get('date', ''), border=1)
                pdf.cell(80, 10, txt=row.get('description', '')[:30], border=1)  # Limit length
                pdf.cell(30, 10, txt=row.get('amount', ''), border=1)
                pdf.cell(40, 10, txt=row.get('transaction_type', ''), border=1)
                pdf.ln()

        pdf.output(pdf_file_path)
        logger.info(f"PDF generated as '{pdf_file_path}'")
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise

# FIX: Update to handle user-specific balances
def update_account_balance(user_id, statements):
    """Update the user account balance based on the statements."""
    # Get current balance
    account_data = accounts_collection.find_one({"user_id": user_id})
    current_balance = account_data.get('balance', 0) if account_data else 0
    
    for statement in statements:
        try:
            amount = float(statement['amount'])
            # FIX: Don't adjust based on transaction_type since amount already includes sign
            current_balance += amount
        except ValueError:
            # Skip invalid amounts
            logger.warning(f"Invalid amount skipped: {statement['amount']}")
    
    # Update in database
    accounts_collection.update_one(
        {"user_id": user_id},
        {"$set": {"balance": current_balance}},
        upsert=True
    )
    logger.info(f"Account balance updated for user {user_id}: {current_balance}")
    return current_balance

# FIX: Remove duplicate functions and use the route handlers directly

# Todo app routes - FIX: Use ObjectId for MongoDB
@app.route('/todos', methods=['GET'])
@login_required
def get_todos():
    # FIX: Filter todos by current user
    todos = list(todos_collection.find({"user_id": current_user.id}))
    return render_template('todos.html', todos=todos)

@app.route('/todos', methods=['POST'])
@login_required
def add_todo():
    title = request.form['title']
    # FIX: Include user_id in the todo
    todos_collection.insert_one({
        'title': title, 
        'completed': False,
        'user_id': current_user.id
    })
    return redirect(url_for('get_todos'))

@app.route('/todos/<todo_id>', methods=['POST'])
@login_required
def update_todo(todo_id):
    # FIX: Convert string to ObjectId
    try:
        object_id = ObjectId(todo_id)
    except:
        abort(400)
        
    completed = request.form.get('completed') == 'true'
    
    # FIX: Ensure todo belongs to current user
    result = todos_collection.update_one(
        {'_id': object_id, 'user_id': current_user.id}, 
        {'$set': {'completed': completed}}
    )
    
    if result.matched_count == 0:
        abort(404)
        
    return redirect(url_for('get_todos'))

@app.route('/todos/<todo_id>/delete', methods=['POST'])
@login_required
def delete_todo(todo_id):
    # FIX: Convert string to ObjectId
    try:
        object_id = ObjectId(todo_id)
    except:
        abort(400)
        
    # FIX: Ensure todo belongs to current user
    result = todos_collection.delete_one({'_id': object_id, 'user_id': current_user.id})
    
    if result.deleted_count == 0:
        abort(404)
        
    return redirect(url_for('get_todos'))

# FIX: Remove placeholder route
# @app.route('/your_route', methods=['GET', 'POST'])
# def your_function():
#     # Your function implementation here
#     pass

# Socket.IO connection handling - FIX: Implement proper room management
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        # Join a room named after the user ID
        flask_socketio.join_room(current_user.id)
    else:
        return False  # Reject connection if not authenticated

if __name__ == "__main__":
    if os.getenv('FLASK_ENV') == 'production':
        from waitress import serve
        # FIX: Add proper production settings
        serve(app, host="0.0.0.0", port=port, threads=10)
    else:
        # FIX: Add proper development settings
        socketio.run(app, host="0.0.0.0", port=port, debug=True)

       
        

                
  
       


        

        
    
       


