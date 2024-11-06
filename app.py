# Proprietary License
# All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.
# © [Sir Pollards Internal Holistic Healing LLC/Terence Pollard Sr.] [2024]

# Code Citations
# This application uses code and libraries from various sources. 
# Please refer to the README.md for detailed information on code usage and attributions.

import os
import csv
import pdfplumber
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from fpdf import FPDF
from markupsafe import escape  # Updated import

app = Flask(__name__)

# Ensure the statements directory exists
if not os.path.exists('statements'):
    os.makedirs('statements')

# Global variable for account balance
account_balance = 848583.68

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    return render_template('index.html', account_balance=account_balance)

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
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise

def correct_discrepancies(statements):
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
    global account_balance
    for statement in statements:
        amount = float(statement['amount'])
        if statement['transaction_type'] == 'deposit':
            account_balance += amount
        elif statement['transaction_type'] == 'withdrawal':
            account_balance -= amount
    logger.info(f"Account balance updated: {account_balance}")

if __name__ == '__main__':
    app.run(port=3000)
