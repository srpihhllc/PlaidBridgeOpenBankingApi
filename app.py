from flask import Flask, jsonify, request
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid import ApiClient, Configuration
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Plaid environment configuration
plaid_env = os.getenv('PLAID_ENV', 'sandbox')
plaid_environments = {
    'sandbox': 'https://sandbox.plaid.com',
    'development': 'https://development.plaid.com',
    'production': 'https://production.plaid.com'
}

if plaid_env not in plaid_environments:
    raise ValueError(f"Invalid PLAID_ENV value: {plaid_env}")

host = plaid_environments[plaid_env]

# Initialize Plaid client
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
    return jsonify({'message': 'Welcome to the Plaid Bridge Open Banking API'})

@app.route('/create-link-token', methods=['POST'])
def create_link_token():
    """
    Creates a link token.

    Returns:
        link_token (str): The generated link token.
    """
    try:
        # Get request data
        request_data = request.json

        # Validate request data
        required_fields = ['client_user_id', 'products', 'country_codes']
        if not all(field in request_data for field in required_fields):
            return jsonify({'error': 'Invalid request data'}), 400

        # Validate products and country codes
        valid_products = {'auth', 'transactions', 'identity', 'assets', 'liabilities', 'income'}
        valid_country_codes = {'US', 'CA', 'GB', 'FR', 'ES', 'NL', 'IE'}

        if not set(request_data['products']).issubset(valid_products):
            return jsonify({'error': 'Invalid products'}), 400

        if not set(request_data['country_codes']).issubset(valid_country_codes):
            return jsonify({'error': 'Invalid country codes'}), 400

        # Create link token request
        link_token_request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(
                client_user_id=request_data['client_user_id']
            ),
            client_name='Plaid Bridge Open Banking API',
            products=[Products(product) for product in request_data['products']],
            country_codes=[CountryCode(country_code) for country_code in request_data['country_codes']],
            language='en'
        )

        # Create link token
        response = client.link_token_create(link_token_request)
        link_token = response.link_token

        return jsonify({'link_token': link_token})
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'Failed to generate link token'}), 500

if __name__ == '__main__':
    app.run(debug=True)
