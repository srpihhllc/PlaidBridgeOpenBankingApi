Proprietary License

All rights reserved. Unauthorized copying, distribution, or modification of this software is strictly prohibited.

© [Sir Pollards Internal Holistic Healing LLC/Terence Pollard Sr.] [2024]


from flask import Flask, render_template, request, jsonify
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.date_range import DateRange
from datetime import datetime, timedelta
import os
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

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

def validate_request_data(data, required_fields):
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

@app.route('/get-account-balances', methods=['POST'])
def get_account_balances():
    """Retrieve account balances."""
    data = request.json
    if not data or 'access_token' not in data:
        return jsonify({'message': 'Invalid request data'}), 400
    
    access_token = data.get('access_token')
    try:
        request = AccountsBalanceGetRequest(access_token=access_token)
        response = client.accounts_balance_get(request)
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while retrieving account balances'}), e.status
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/get-transactions', methods=['POST'])
def get_transactions():
    """Retrieve transactions for the past 6 months."""
    data = request.json
    if not data or 'access_token' not in data:
        return jsonify({'message': 'Invalid request data'}), 400
    
    access_token = data.get('access_token')
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=180)  # 6 months ago
    try:
        options = TransactionsGetRequestOptions()
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=options
        )
        response = client.transactions_get(request)
        return jsonify(response.to_dict())
    except plaid.ApiException as e:
        logger.error(f"Plaid API Error: {e}")
        return jsonify({'error': 'An error occurred while retrieving transactions'}), e.status
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
            response = verify_truelayer(access_token)
        elif platform == 'basiq':
            response = verify_basiq(access_token)
        elif platform == 'codat':
            response = verify_codat(access_token)
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
    return {'status': 'success', 'message': 'TrueLayer verification successful'}

def verify_basiq(access_token: str) -> Dict:
    """Verify lender information using Basiq."""
    # Implement Basiq verification logic here
    return {'status': 'success', 'message': 'Basiq verification successful'}

def verify_codat(access_token: str) -> Dict:
    """Verify lender information using Codat."""
    # Implement Codat verification logic here
    return {'status': 'success', 'message': 'Codat verification successful'}

@app.route('/webhook/plaid', methods=['POST'])
def plaid_webhook():
    """Handle Plaid webhooks."""
    data = request.json
    logger.info(f"Received Plaid webhook: {data}")
    return jsonify({'status': 'received'}), 200

@app.route('/webhook/treasuryprime', methods=['POST'])
def treasury_prime_webhook():
    """Handle Treasury Prime webhooks."""
    data = request.json
    logger.info(f"Received Treasury Prime webhook: {data}")
    return jsonify({'status': 'received'}), 200

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)

   
       
        

                
  
       


        

        
    
       
