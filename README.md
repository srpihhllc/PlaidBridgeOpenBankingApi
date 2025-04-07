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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')
socketio = SocketIO(app)

# Get the PORT from environment variables
port = int(os.getenv("PORT", 3000))

# Ensure the statements directory exists
app.config['UPLOAD_FOLDER'] = 'statements'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit file size to 16MB

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Global variable for account balance
account_balance = 848583.68

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Starting application")

# Plaid API configuration
configuration = Configuration(
    host="https://sandbox.plaid.com",
    api_key={
        'clientId': os.getenv('PLAID_CLIENT_ID'),
        'secret': os.getenv('PLAID_SECRET')
    }
)
api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)

# Treasury Prime API configuration
treasury_prime_env = os.getenv('TREASURY_PRIME_ENV', 'sandbox')
if treasury_prime_env == 'production':
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_PRODUCTION_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_PRODUCTION_API_URL')
else:
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_SANDBOX_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_SANDBOX_API_URL')

if TREASURY_PRIME_API_URL is None:
    raise ValueError("TREASURY_PRIME_API_URL is not set in the environment variables.")

# MongoDB configuration
mongo_client = MongoClient(os.getenv('COSMOS_DB_CONNECTION_STRING'))
db = mongo_client['plaidbridgeopenbankingapi-database']
todos_collection = db['todos']

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        user = User(user_id)
        login_user(user)
        return redirect(url_for('home'))
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
    # Mock data for account information
    statements = [
        {'date': '2024-01-01', 'description': 'Deposit', 'amount': '1577.56'},
        {'date': '2023-01-02', 'description': 'Withdrawal', 'amount': '-550.38'}
    ]
    return render_template('account_info.html', account_balance=account_balance, statements=statements)

@app.route('/create_link_token', methods=['GET'])
@login_required
def create_link_token():
    try:
        response = plaid_client.LinkToken.create({
            'user': {
                'client_user_id': 'unique_user_id'
            },
            'client_name': 'PlaidBridgeOpenBankingAPI',
            'products': ['auth'],
            'country_codes': ['US'],
            'language': 'en',
            'redirect_uri': 'https://yourapp.com/oauth-return',
        })
        return jsonify({'link_token': response['link_token']})
    except Exception as e:
        logger.error(f"Error creating Plaid link token: {e}")
        return jsonify({'message': 'Error creating link token'}), 500

@app.route('/exchange_public_token', methods=['POST'])
@login_required
def exchange_public_token():
    data = request.json
    try:
        response = plaid_client.Item.public_token.exchange(data['public_token'])
        access_token = response['access_token']
        return jsonify({'access_token': access_token})
    except Exception as e:
        logger.error(f"Error exchanging Plaid public token: {e}")
        return jsonify({'message': 'Error exchanging public token'}), 500

@app.route('/upload-pdf', methods=['POST'])
@login_required
def upload_pdf():
    global account_balance
    if 'file' not in request.files:
        logger.error("No file part in the request")
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': 
        logger.error("No selected file")
        return jsonify({'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        try:
            statements = parse_pdf(file_path)
            corrected_statements = correct_discrepancies(statements)
            csv_filename = filename.replace('.pdf', '.csv')
            csv_file_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            save_statements_as_csv(corrected_statements, csv_file_path)
            update_account_balance(corrected_statements)
            logger.info(f"File processed successfully: {filename}")
            socketio.emit('update', {'account_balance': account_balance, 'statements': corrected_statements})
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
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'message': 'Error downloading file'}), 500

@app.route('/generate-pdf/<csv_filename>', methods=['GET'])
@login_required
def generate_pdf(csv_filename):
    try:
        base_path = app.config['UPLOAD_FOLDER']
        
        # Normalize and validate csv_filename
        csv_file_path = os.path.normpath(os.path.join(base_path, csv_filename))
        if not csv_file_path.startswith(base_path):
            raise Exception("Invalid file path for CSV file")

        pdf_filename = csv_filename.replace('.csv', '.pdf')
        
        # Normalize and validate pdf_filename
        pdf_file_path = os.path.normpath(os.path.join(base_path, pdf_filename))
        if not pdf_file_path.startswith(base_path):
            raise Exception("Invalid file path for PDF file")

        generate_pdf_from_csv(csv_file_path, pdf_file_path)
        return send_from_directory(app.config['UPLOAD_FOLDER'], pdf_filename)
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'message': 'Error generating PDF'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

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

def parse_page(text):
    """Parse a single page of text to extract statements."""
    statements = []
    for line in text.split('\n'):
        parts = line.split()
        if len(parts) >= 3:
            date = parts[0]
            description = " ".join(parts[1:-1])
            amount = parts[-1]
            # Determine if the amount is a deposit or withdrawal
            if amount.startswith('-'):
                transaction_type = 'withdrawal'
            else:
                transaction_type = 'deposit'
            statements.append({
                'date': date,
                'description': description,
                'amount': amount,
                'transaction_type': transaction_type
            })
    return statements

def correct_discrepancies(statements):
    """Correct discrepancies in the statements."""
    corrected_statements = []
    for statement in statements:
        try:
            amount = float(statement['amount'])
            corrected_statements.append(statement)
        except ValueError:
            # Handle misprints or miscalculations
            statement['amount'] = '0.00'  # Set to zero or some default value
            corrected_statements.append(statement)
    return corrected_statements

def save_statements_as_csv(statements, file_path):
    """Save the statements as a CSV file."""
    try:
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

        with open(csv_file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                line = f"{row['date']} {row['description']} {row['amount']} {row['transaction_type']}"
                pdf.cell(200, 10, txt=line, ln=True)

        pdf.output(pdf_file_path)
        logger.info(f"PDF generated as '{pdf_file_path}'")
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise

def update_account_balance(statements):
    """Update the global account balance based on the statements."""
    global account_balance
    for statement in statements:
        amount = float(statement['amount'])
        if statement['transaction_type'] == 'deposit':
            account_balance += amount
        elif statement['transaction_type'] == 'withdrawal':
            account_balance -= amount
    logger.info(f"Account balance updated: {account_balance}")

# Plaid API integration
def create_plaid_link_token():
    try:
        response = plaid_client.LinkToken.create({
            'user': {
                'client_user_id': 'unique_user_id'
            },
            'client_name': 'PlaidBridgeOpenBankingAPI',
            'products': ['auth'],
            'country_codes': ['US'],
            'language': 'en',
            'redirect_uri': 'https://yourapp.com/oauth-return',
        })
        return response['link_token']
    except Exception as e:
        logger.error(f"Error creating Plaid link token: {e}")
        raise

def exchange_plaid_public_token(public_token):
    try:
        response = plaid_client.Item.public_token.exchange(public_token)
        return response['access_token']
    except Exception as e:
        logger.error(f"Error exchanging Plaid public token: {e}")
        raise

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
        logger.error(f"Error verifying Treasury Prime account: {e}")
        raise

# Additional functionalities for micro deposits, account linking, fund transfers, notifications, and handling delinquencies

@app.route('/your_route', methods=['GET', 'POST'])
def your_function():
    # Your function implementation here
    pass

# Todo app routes
@app.route('/todos', methods=['GET'])
@login_required
def get_todos():
    todos = list(todos_collection.find())
    return render_template('todos.html', todos=todos)

@app.route('/todos', methods=['POST'])
@login_required
def add_todo():
    title = request.form['title']
    todos_collection.insert_one({'title': title, 'completed': False})
    return redirect(url_for('get_todos'))

@app.route('/todos/<int:todo_id>', methods=['POST'])
@login_required
def update_todo(todo_id):
    completed = request.form['completed'] == 'true'
    todos_collection.update_one({'_id': todo_id}, {'$set': {'completed': completed}}) 
    return redirect(url_for('get_todos'))

@app.route('/todos/<int:todo_id>/delete', methods=['POST'])
@login_required
def delete_todo(todo_id):
    todos_collection.delete_one({'_id': todo_id})
    return redirect(url_for('get_todos'))

if __name__ == "__main__":
    if os.getenv('FLASK_ENV') == 'production':
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    else:
        socketio.run(app, host="0.0.0.0", port=port)   
                
  
       


        

        
    
       
