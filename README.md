from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def hello_world():
    return render_template("index.html", title="Hello")
"""
Proprietary License

All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.

© [Sir Pollards Internal Holistic Healing LLC/Terence Pollard Sr.] [2024]
"""

import os
import csv
import pdfplumber
import logging
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from fpdf import FPDF
from plaid import Client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

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
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_ENV = os.getenv('PLAID_ENV', 'sandbox')  # Use 'sandbox' for testing

# Initialize Plaid client
plaid_client = Client(client_id=PLAID_CLIENT_ID, secret=PLAID_SECRET, environment=PLAID_ENV)

# Treasury Prime API configuration
TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_API_KEY')
TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_API_URL')  # Read from environment

if TREASURY_PRIME_API_URL is None:
    raise ValueError("TREASURY_PRIME_API_URL is not set in the environment variables.")

@app.route('/')
def index():
    return render_template('index.html', account_balance=account_balance)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

@app.route('/upload-pdf', methods=['POST'])
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
def download_statement(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'message': 'Error downloading file'}), 500

@app.route('/generate-pdf/<csv_filename>', methods=['GET'])
def generate_pdf(csv_filename):
    try:
        csv_file_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
        pdf_filename = csv_filename.replace('.csv', '.pdf')
        pdf_file_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        generate_pdf_from_csv(csv_file_path, pdf_file_path)
        return send_from_directory(app.config['UPLOAD_FOLDER'], pdf_filename)
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'message': 'Error generating PDF'}), 500

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

   
       
        

                
  
       


        

        
    
       
