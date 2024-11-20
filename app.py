from flask import Flask, jsonify, request, render_template
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
    return render_template('index.html')

@app.route('/create-link-token', methods=['GET'])
def create_link_token():
    try:
        request_data = {
            "client_user_id": "unique_user_id",
            "products": ["auth"],
            "country_codes": ["US"]
        }

        link_token_request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(
                client_user_id=request_data['client_user_id']
            ),
            client_name='Plaid Bridge Open Banking API',
            products=[Products(product) for product in request_data['products']],
            country_codes=[CountryCode(country_code) for country_code in request_data['country_codes']],
            language='en'
        )

        response = client.link_token_create(link_token_request)
        link_token = response.link_token

        return jsonify({'link_token': link_token})
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'Failed to generate link token'}), 500

@app.route('/exchange-public-token', methods=['POST'])
def exchange_public_token():
    public_token = request.json.get('public_token')
    try:
        response = client.item_public_token_exchange({'public_token': public_token})
        access_token = response['access_token']
        item_id = response['item_id']
        return jsonify({'access_token': access_token, 'item_id': item_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify-account', methods=['POST'])
def verify_account():
    account_id = request.json.get('account_id')
    # Implement your account verification logic here
    # For example, you might use the access token to fetch account details
    # and verify the account ID
    try:
        # Placeholder response for demonstration purposes
        account_info = {
            'account_id': account_id,
            'verified': True
        }
        return jsonify({'account_info': account_info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
      
