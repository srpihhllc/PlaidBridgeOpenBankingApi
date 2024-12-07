Proprietary License

All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.

© [Sir Pollards Internal Holistic Healing LLC/Terence Pollard Sr.] [2024]


from flask import Flask, render_template, request, jsonify
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.payment_initiation_payment_create_request import PaymentInitiationPaymentCreateRequest
from plaid.model.payment_initiation_payment_token_create_request import PaymentInitiationPaymentTokenCreateRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.auth_get_request import AuthGetRequest
from plaid.model.transfer_authorization_create_request import TransferAuthorizationCreateRequest
from plaid.model.transfer_create_request import TransferCreateRequest
from plaid.model.transfer_create_response import TransferCreateResponse
from plaid import ApiClient, Configuration
import os
import logging
from werkzeug.utils import secure_filename
import pdfplumber
from typing import Dict
from datetime import datetime, timedelta
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['UPLOAD_FOLDER'] = 'uploads'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Determine the Plaid environment
plaid_env = os.getenv('PLAID_ENV', 'sandbox')
if plaid_env not in ['sandbox', 'development', 'production']:
    raise ValueError(f"Invalid PLAID_ENV value: {plaid_env}")

host = f'https://{plaid_env}.plaid.com'

# Initialize the Plaid client
configuration = Configuration(
    host=host,
    api_key={
        'clientId': os.getenv('PLAID_CLIENT_ID'),
        'secret': os.getenv('PLAID_SECRET')
    }
)
api_client = ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

def validate_request_data(data: Dict, required_fields: list) -> bool:
    """Validate the request data."""
    return all(field in data for field in required_fields)

@app.route('/')
def index():
    """Render the index template."""
    return render_template('index.html')

@app.route('/exchange-public-token', methods=['POST'])
def exchange_public_token():
    """Exchange the public token for an access token."""
    data = request.json
    if not data or 'public_token' not in data:
        return jsonify({'message': 'Invalid request data'}), 400
    
    public_token = data.get('public_token')
    try:
        response = client.item_public_token_exchange({'public_token': public_token})
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while exchanging the public token'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/create-link-token', methods=['POST'])
def create_link_token():
    """Create a link token."""
    try:
        request_data = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id='unique_user_id'),
            client_name='PlaidBridgeOpenBankingAPI',
            products=[Products('auth')],
            country_codes=[CountryCode('US')],
            language='en'
        )
        response = client.link_token_create(request_data)
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while creating the link token'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/create-payment-token', methods=['POST'])
def create_payment_token():
    """Create a payment token."""
    data = request.json
    if not validate_request_data(data, ['public_token', 'recipient_id', 'reference', 'amount']):
        return jsonify({'message': 'Invalid request data'}), 400
    
    try:
        payment_request = PaymentInitiationPaymentCreateRequest(
            recipient_id=data.get('recipient_id'),
            reference=data.get('reference'),
            amount={
                'currency': 'USD',
                'value': data.get('amount')
            }
        )
        payment_response = client.payment_initiation_payment_create(payment_request)
        payment_id = payment_response['payment_id']

        token_request = PaymentInitiationPaymentTokenCreateRequest(payment_id=payment_id)
        token_response = client.payment_initiation_payment_token_create(token_request)
        return jsonify(token_response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while creating the payment token'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/make-payment', methods=['POST'])
def make_payment():
    """Make a payment."""
    data = request.json
    if not validate_request_data(data, ['public_token', 'recipient_id', 'reference', 'amount']):
        return jsonify({'message': 'Invalid request data'}), 400
    
    try:
        payment_data = {
            'recipient_id': data.get('recipient_id'),
            'reference': data.get('reference'),
            'amount': data.get('amount')
        }
        plaid_api = get_plaid_bridge_api()
        response = plaid_api.process_payment(payment_data)
        return jsonify(response)
    except ValueError as e:
        logger.error(f"Validation Error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/verify-account', methods=['POST'])
def verify_account():
    """Verify account information."""
    data = request.json
    if not data or 'access_token' not in data:
        return jsonify({'message': 'Invalid request data'}), 400
    
    access_token = data.get('access_token')
    try:
        request = AuthGetRequest(access_token=access_token)
        response = client.auth_get(request)
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while verifying the account'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/get-account-info', methods=['POST'])
def get_account_info():
    """Get account information."""
    data = request.json
    if not data or 'access_token' not in data:
        return jsonify({'message': 'Invalid request data'}), 400
    
    access_token = data.get('access_token')
    try:
        request = AccountsGetRequest(access_token=access_token)
        response = client.accounts_get(request)
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while retrieving account information'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/verify-lender', methods=['POST'])
def verify_lender():
    """Verify lender information using different platforms."""
    data = request.json
    if not data or 'platform' not in data or 'access_token' not in data:
        return jsonify({'message': 'Invalid request data'}), 400
    
    platform = data.get('platform')
    access_token = data.get('access_token')
    
    try:
        if platform == 'plaid':
            request = AuthGetRequest(access_token=access_token)
            response = client.auth_get(request)
        elif platform == 'truelayer':
            # Implement TrueLayer verification logic here
            response = verify_truelayer(access_token)
        elif platform == 'basio':
            # Implement Basio verification logic here
            response = verify_basio(access_token)
        else:
            return jsonify({'message': 'Unsupported platform'}), 400
        
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while verifying the lender'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

def verify_truelayer(access_token: str) -> Dict:
    """Verify lender information using TrueLayer."""
    # Implement TrueLayer verification logic here
    # This is a placeholder function
    return {'status': 'success', 'message': 'TrueLayer verification successful'}

def verify_basio(access_token: str) -> Dict:
    """Verify lender information using Basio."""
    # Implement Basio verification logic here
    # This is a placeholder function
    return {'status': 'success', 'message': 'Basio verification successful'}

@app.route('/webhook/plaid', methods=['POST'])
def plaid_webhook():
    """Handle Plaid webhooks."""
    data = request.json
    logger.info(f"Received Plaid webhook: {data}")
    # Process the webhook data
    return jsonify({'status': 'received'}), 200

@app.route('/webhook/treasuryprime', methods=['POST'])
def treasury_prime_webhook():
    """Handle Treasury Prime webhooks."""
    data = request.json
    logger.info(f"Received Treasury Prime webhook: {data}")
    # Process the webhook data
    return jsonify({'status': 'received'}), 200

@app.route('/upload-statement', methods=['POST'])
def upload_statement():
    """Upload and verify PDF statements."""
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        # Process the PDF file
        with pdfplumber.open(filepath) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text()
            # Here you can implement logic to verify the statement
            logger.info(f"Extracted text from PDF: {text}")
        return jsonify({'message': 'File uploaded and processed successfully'}), 200
    else:
        return jsonify({'message': 'Invalid file type'}), 400

@app.route('/initiate-transfer', methods=['POST'])
def initiate_transfer():
    """Initiate a transfer between accounts."""
    data = request.json
    if not validate_request_data(data, ['access_token', 'amount', 'from_account_id', 'to_account_id']):
        return jsonify({'message': 'Invalid request data'}), 400
    
    access_token = data.get('access_token')
    amount = data.get('amount')
    from_account_id = data.get('from_account_id')
    to_account_id = data.get('to_account_id')
    
    try:
        # Create a transfer authorization
        auth_request = TransferAuthorizationCreateRequest(
            access_token=access_token,
            amount=amount,
            from_account_id=from_account_id,
            to_account_id=to_account_id
        )
        auth_response = client.transfer_authorization_create(auth_request)
        
        # Create the transfer
        transfer_request = TransferCreateRequest(
            authorization_id=auth_response.authorization.id,
            amount=amount,
            from_account_id=from_account_id,
            to_account_id=to_account_id
        )
        transfer_response = client.transfer_create(transfer_request)
        return jsonify(transfer_response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while initiating the transfer'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

def schedule_notifications(lender_id: str, payment_date: datetime):
    """Schedule notifications for lenders."""
    def send_notification(lender_id: str, message: str):
        # Implement the logic to send notification to the lender
        logger.info(f"Notification to lender {lender_id}: {message}")

    # Schedule 48-hour notification
    notification_48_hours = payment_date - timedelta(hours=48)
    threading.Timer((notification_48_hours - datetime.now()).total_seconds(), send_notification, args=[lender_id, "48-hour payment reminder"]).start()

    # Schedule day-of-payment notification
    notification_day_of = payment_date
    threading.Timer((notification_day_of - datetime.now()).total_seconds(), send_notification, args=[lender_id, "Payment due today"]).start()

@app.route('/schedule-payment', methods=['POST'])
def schedule_payment():
    """Schedule a payment and notifications for lenders."""
    data = request.json
    if not validate_request_data(data, ['lender_id', 'payment_date']):
        return jsonify({'message': 'Invalid request data'}), 400
    
    lender_id = data.get('lender_id')
    payment_date = datetime.strptime(data.get('payment_date'), '%Y-%m-%d %H:%M:%S')
    
    schedule_notifications(lender_id, payment_date)
    return jsonify({'message': 'Payment and notifications scheduled successfully'}), 200

@app.route('/check-delinquency', methods=['POST'])
def check_delinquency():
    """Check if the borrower is delinquent and stop transactions if necessary."""
    data = request.json
    if not validate_request_data(data, ['borrower_id', 'lender_id']):
        return jsonify({'message': 'Invalid request data'}), 400
    
    borrower_id = data.get('borrower_id')
    lender_id = data.get('lender_id')
    
    # Implement logic to check if the borrower is delinquent
    is_delinquent = False  # Placeholder for actual delinquency check
    
    if is_delinquent:
        # Implement logic to stop transactions
        logger.info(f"Transactions stopped for borrower {borrower_id} due to delinquency")
        return jsonify({'message': 'Borrower is delinquent. Transactions stopped.'}), 200
    else:
        return jsonify({'message': 'Borrower is not delinquent.'}), 200

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)

   
       
        

                
  
       


        

        
    
       
