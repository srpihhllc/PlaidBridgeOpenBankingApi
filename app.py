from flask import Flask, render_template, request, jsonify
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid import ApiClient, Configuration
import os
import logging
import re

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
    if not public_token or not re.match(r'^[a-zA-Z0-9-_]+$', public_token):
        return jsonify({'message': 'Invalid public token'}), 400
    try:
        response = client.item_public_token_exchange({'public_token': public_token})
        return jsonify(response.to_dict())
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An error occurred while exchanging the public token'}), 500

if __name__ == '__main__':
    app.run(debug=True)
