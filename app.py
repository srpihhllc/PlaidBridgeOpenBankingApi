from flask import Flask, render_template, request, jsonify
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid import ApiClient, Configuration
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Plaid client
configuration = Configuration(
    host=Configuration.Host.SANDBOX,
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

@app.route('/create_link_token', methods=['POST'])
def create_link_token():
    try:
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id='unique_user_id'),
            client_name='PlaidBridgeOpenBankingAPI',
            products=[Products('auth')],
            country_codes=[CountryCode('US')],
            language='en'
        )
        response = client.link_token_create(request)
        return jsonify(response.to_dict())
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/exchange_public_token', methods=['POST'])
def exchange_public_token():
    try:
        public_token = request.json['public_token']
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = client.item_public_token_exchange(exchange_request)
        access_token = response['access_token']
        return jsonify({'access_token': access_token})
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/accounts', methods=['POST'])
def get_accounts():
    try:
        access_token = request.json['access_token']
        accounts_request = AccountsGetRequest(access_token=access_token)
        response = client.accounts_get(accounts_request)
        return jsonify(response.to_dict())
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
   
       
