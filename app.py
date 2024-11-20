from flask import Flask, render_template, request, jsonify
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid import ApiClient, Configuration
import os
import logging

# Ensure the pay.plaidbridgeopenbankingapi module is installed
# pip install pay.plaidbridgeopenbankingapi

import pay.plaidbridgeopenbankingapi

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Determine the Plaid environment
plaid_env = os.getenv('PLAID_ENV', 'sandbox')
if plaid_env == 'sandbox':
    host = 'https://sandbox.plaid.com'
elif plaid_env == 'development':
    host = 'https://development.plaid.com'
elif plaid_env == 'production':
    host = 'https://production.plaid.com'
else:
    raise ValueError(f"Invalid PLAID_ENV value: {plaid_env}")

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/exchange-public-token', methods=['POST'])
def exchange_public_token():
    public_token = request.json.get('public_token')
    if not public_token:
        return jsonify({'message': 'Public token is required'}), 400
    try:
        response = client.item_public_token_exchange(public_token)
        return jsonify(response.to_dict())
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/create-link-token', methods=['POST'])
def create_link_token():
    try:
        request_data = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id='unique_user_id'),
            client_name='PlaidBridgeOpenBankingAPI',
            products=[Products('auth')],
            country_codes=[CountryCode('US')],
            language='en'
        )
        logger.info(f"Request Data: {request_data}")
        response = client.link_token_create(request_data)
        return jsonify(response.to_dict())
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/make-payment', methods=['POST'])
def make_payment():
    payment_data = request.json
    try:
        # Assuming pay.plaidbridgeopenbankingapi is a module or service you have
        response = pay.plaidbridgeopenbankingapi.process_payment(payment_data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
