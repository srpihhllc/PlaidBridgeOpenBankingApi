# =============================================================================
# FILE: app/services/plaid_api.py
# DESCRIPTION: Cockpit‑grade Plaid API integration service.
#              Provides link token generation, credential verification,
#              and transaction retrieval with robust error handling.
# =============================================================================

import json
import os
from datetime import datetime, timedelta

from flask import jsonify
from plaid.api.plaid_api import PlaidApi

# ✅ Correct Plaid imports
from plaid.api_client import ApiClient
from plaid.configuration import Configuration
from plaid.exceptions import ApiException
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.transactions_get_request import TransactionsGetRequest

# -----------------------------------------------------------------------------
# Environment configuration
# -----------------------------------------------------------------------------
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")  # 'sandbox', 'development', or 'production'

if not PLAID_CLIENT_ID or not PLAID_SECRET:
    raise RuntimeError("❌ Missing Plaid API credentials. Check environment variables.")

configuration = Configuration(
    host=f"https://{PLAID_ENV}.plaid.com",
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
api_client = ApiClient(configuration)
plaid_client = PlaidApi(api_client)


# -----------------------------------------------------------------------------
# Link Token Generation
# -----------------------------------------------------------------------------
def generate_link_token(user_id: str):
    """
    Creates a Plaid Link Token for user authentication.
    Returns JSON with {"link_token": "..."} or {"error": "..."}.
    """
    try:
        request = LinkTokenCreateRequest(
            client_name="PlaidBridge Open Banking API",
            language="en",
            country_codes=["US"],
            user={"client_user_id": str(user_id)},
            products=["auth", "transactions"],
        )
        response = plaid_client.link_token_create(request)
        return jsonify({"link_token": response.link_token})
    except ApiException as e:
        error_body = {}
        try:
            error_body = json.loads(e.body) if hasattr(e, "body") else {}
        except Exception:
            pass
        return jsonify({"error": error_body.get("error_message", str(e))}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Alias for backward compatibility (fixes api_routes.py import)
create_link_token = generate_link_token


# -----------------------------------------------------------------------------
# Verify Lender Credentials
# -----------------------------------------------------------------------------
def verify_via_plaid(plaid_token: str):
    """
    Verifies lender credentials via Plaid API by fetching a small transaction window.
    Returns dict of transactions or error JSON.
    """
    try:
        request = TransactionsGetRequest(
            access_token=plaid_token,
            start_date="2024-05-01",
            end_date="2024-06-01",
        )
        response = plaid_client.transactions_get(request)
        return response.to_dict()
    except ApiException as e:
        try:
            error_body = json.loads(e.body)
        except Exception:
            error_body = {}
        return jsonify({"error": error_body.get("error_message", str(e))}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# Fetch Transactions
# -----------------------------------------------------------------------------
def get_transactions(access_token: str, start_date: str = None, end_date: str = None):
    """
    Retrieves transactions for a given access token.
    Defaults to last 30 days if no dates provided.
    Returns JSON with {"transactions": [...]} or {"error": "..."}.
    """
    if not access_token:
        return jsonify({"error": "Missing access token"}), 400

    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
        )
        response = plaid_client.transactions_get(request)
        # Convert to dict for JSON safety
        transactions = [txn.to_dict() for txn in response.transactions]
        return jsonify({"transactions": transactions})
    except ApiException as e:
        try:
            error_body = json.loads(e.body)
        except Exception:
            error_body = {}
        return jsonify({"error": error_body.get("error_message", str(e))}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
