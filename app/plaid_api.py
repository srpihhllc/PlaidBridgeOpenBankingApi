import os
from plaid import ApiClient, Configuration
from plaid.api.plaid_api import PlaidApi
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from flask import jsonify
from datetime import datetime, timedelta

# ✅ Load environment variables
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")  # Use 'sandbox', 'development', or 'production'

# ✅ Configure Plaid API Client
configuration = Configuration(
    host=f"https://{PLAID_ENV}.plaid.com",
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
api_client = ApiClient(configuration)
plaid_client = PlaidApi(api_client)


# ✅ Generate a Link Token
def generate_link_token(user_id: str):
    """Creates a Plaid Link Token for user authentication."""
    try:
        request = LinkTokenCreateRequest(
            client_name="PlaidBridge Open Banking API",
            language="en",
            country_codes=["US"],
            user={"client_user_id": user_id},
            products=["auth", "transactions"]
        )
        response = plaid_client.link_token_create(request)
        return jsonify({"link_token": response["link_token"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Fetch Transactions from Plaid
def get_transactions(access_token: str, start_date=None, end_date=None):
    """Retrieves transactions for a given access token."""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
        )
        response = plaid_client.transactions_get(request)
        return jsonify({"transactions": response["transactions"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
