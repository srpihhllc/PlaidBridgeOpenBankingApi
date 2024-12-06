from flask import Flask, render_template, request, jsonify
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.payment_initiation_payment_create_request import PaymentInitiationPaymentCreateRequest
from plaid.model.payment_initiation_payment_token_create_request import PaymentInitiationPaymentTokenCreateRequest
from plaid import ApiClient, Configuration
import os
import logging
from plaid_bridge_open_banking_api import get_plaid_bridge_api
from typing import Dict

app = Flask(__name__)

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

def validate_request_data(data: Dict) -> bool:
    """Validate the request data."""
    required_fields = ['public_token', 'recipient_id', 'reference', 'amount']
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
    if not validate_request_data(data):
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
    if not validate_request_data(data):
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
