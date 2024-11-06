import os
import csv
import pdfplumber
import logging
import requests
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from fpdf import FPDF
from markupsafe import escape
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Ensure the statements directory exists
if not os.path.exists('statements'):
    os.makedirs('statements')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS account_balance (
            id INTEGER PRIMARY KEY,
            balance REAL NOT NULL
        )
    ''')
    cursor.execute('''
        INSERT INTO account_balance (id, balance)
        SELECT 1, 848583.68
        WHERE NOT EXISTS (SELECT 1 FROM account_balance WHERE id = 1)
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    account_balance = get_account_balance()
    return render_template('index.html', account_balance=account_balance)

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        logger.error("No file part in the request")
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        logger.error("No selected file")
        return jsonify({'message': 'No selected file'}), 400
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        file_path = os.path.join('statements', filename)
        file.save(file_path)
        try:
            statements = parse_pdf(file_path)
            corrected_statements = correct_discrepancies(statements)
            csv_filename = filename.replace('.pdf', '.csv')
            csv_file_path = os.path.join('statements', csv_filename)
            save_statements_as_csv(corrected_statements, csv_file_path)
            update_account_balance(corrected_statements)
            logger.info(f"File processed successfully: {filename}")
            return jsonify({'message': 'File processed successfully', 'csv_file': csv_filename}), 200
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            return jsonify({'message': 'Error processing file'}), 500
    logger.error("Invalid file format")
    return jsonify({'message': 'Invalid file format'}), 400

@app.route('/statements/<filename>')
def download_statement(filename):
    try:
        return send_from_directory('statements', filename)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'message': 'Error downloading file'}), 500

@app.route('/generate-pdf/<csv_filename>', methods=['GET'])
def generate_pdf(csv_filename):
    try:
        csv_file_path = os.path.join('statements', csv_filename)
        pdf_filename = csv_filename.replace('.csv', '.pdf')
        pdf_file_path = os.path.join('statements', pdf_filename)
        generate_pdf_from_csv(csv_file_path, pdf_file_path)
        return send_from_directory('statements', pdf_filename)
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'message': 'Error generating PDF'}), 500

def parse_pdf(file_path):
    statements = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        parts = line.split()
                        if len(parts) >= 3:
                            date = parts[0]
                            description = " ".join(parts[1:-1])
                            amount = parts[-1]
                            transaction_type = 'withdrawal' if amount.startswith('-') else 'deposit'
                            statements.append({
                                'date': date,
                                'description': description,
                                'amount': amount,
                                'transaction_type': transaction_type
                            })
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise
    return statements

def correct_discrepancies(statements):
    corrected_statements = []
    for statement in statements:
        try:
            amount = float(statement['amount'])
            corrected_statements.append(statement)
        except ValueError:
            statement['amount'] = '0.00'
            corrected_statements.append(statement)
    return corrected_statements

def save_statements_as_csv(statements, file_path):
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
    account_balance = get_account_balance()
    for statement in statements:
        amount = float(statement['amount'])
        if statement['transaction_type'] == 'deposit':
            account_balance += amount
        elif statement['transaction_type'] == 'withdrawal':
            account_balance -= amount
    set_account_balance(account_balance)
    logger.info(f"Account balance updated: {account_balance}")

def get_account_balance():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM account_balance WHERE id = 1')
    balance = cursor.fetchone()[0]
    conn.close()
    return balance

def set_account_balance(balance):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE account_balance SET balance = ? WHERE id = 1', (balance,))
    conn.commit()
    conn.close()

def integrate_with_piermont_treasury_prime():
    try:
        response = requests.post(
            os.getenv('PIERMONT_TREASURY_PRIME_API_URL'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {os.getenv("PIERMONT_TREASURY_PRIME_ACCESS_TOKEN")}'
            },
            json={
                'client_id': os.getenv('PIERMONT_TREASURY_PRIME_CLIENT_ID'),
                'secret': os.getenv('PIERMONT_TREASURY_PRIME_SECRET')
            }
        )
        if response.status_code == 200:
            logger.info('Successfully integrated with Piermont Treasury Prime')
            return response.json()
        else:
            logger.error('Failed to integrate with Piermont Treasury Prime')
            return None
    except Exception as e:
        logger.error(f"Error integrating with Piermont Treasury Prime: {e}")
        return None

if __name__ == '__main__':
    integrate_with_piermont_treasury_prime()
    app.run(port=3000)
