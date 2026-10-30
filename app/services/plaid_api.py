# =============================================================================
# FILE: app/services/plaid_api.py
# DESCRIPTION: Cockpit‑grade Plaid API integration service.
#                Provides link token generation, credential verification,
#                transaction retrieval, and token exchange with robust error handling.
# =============================================================================

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple, Union, cast

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import (
    LinkTokenCreateRequestUser,
)
from plaid.model.products import Products
from plaid.model.transactions_get_request import TransactionsGetRequest

# -----------------------------------------------------------------------------
# Environment & Client Initialization
# -----------------------------------------------------------------------------
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox").lower()

if not PLAID_CLIENT_ID or not PLAID_SECRET:
    raise RuntimeError(
        "❌ Missing Plaid API credentials. Check environment variables."
    )

# Map environment string to Plaid SDK host
HOST_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}
plaid_host = HOST_MAP.get(PLAID_ENV, plaid.Environment.Sandbox)

configuration = plaid.Configuration(
    host=plaid_host,
    api_key={
        "clientId": PLAID_CLIENT_ID,
        "secret": PLAID_SECRET,
    },
)

api_client = plaid.ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)


def get_plaid_client() -> plaid_api.PlaidApi:
    """Returns the configured Plaid API client instance."""
    return plaid_client


# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------
def _parse_api_error(e: ApiException) -> str:
    """Extracts human-readable error messages from Plaid ApiException bodies."""
    try:
        body = json.loads(e.body) if hasattr(e, "body") and e.body else {}
        err_message = body.get("error_message")
        return str(err_message) if err_message else str(e)
    except Exception:
        return str(e)


# -----------------------------------------------------------------------------
# Link Token Generation
# -----------------------------------------------------------------------------
def generate_link_token(
    user_id: str,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Creates a Plaid Link Token for user authentication.
    Returns a dictionary payload or error tuple for route serialization.
    """
    try:
        req = LinkTokenCreateRequest(
            client_name="PlaidBridge Open Banking API",
            language="en",
            country_codes=[CountryCode("US")],
            products=[Products("auth"), Products("transactions")],
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
        )
        response = plaid_client.link_token_create(req)
        return {"link_token": response["link_token"]}
    except ApiException as e:
        return {"error": _parse_api_error(e)}, 500
    except Exception as e:
        return {"error": str(e)}, 500


# Alias for backward compatibility
create_link_token = generate_link_token


# -----------------------------------------------------------------------------
# Verify Lender Credentials
# -----------------------------------------------------------------------------
def verify_via_plaid(
    plaid_token: str,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Verifies credentials via Plaid API by fetching a small transaction window.
    Returns transaction dict on success or standardized error tuple on failure.
    """
    try:
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        end_date = datetime.now(timezone.utc).date()

        req = TransactionsGetRequest(
            access_token=plaid_token,
            start_date=start_date,
            end_date=end_date,
        )
        response = plaid_client.transactions_get(req)
        return cast(Dict[str, Any], response.to_dict())
    except ApiException as e:
        return {"error": _parse_api_error(e)}, 500
    except Exception as e:
        return {"error": str(e)}, 500


# -----------------------------------------------------------------------------
# Fetch Transactions
# -----------------------------------------------------------------------------
def get_transactions(
    access_token: str,
    start_date: Union[str, None] = None,
    end_date: Union[str, None] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Retrieves transactions for a given access token.
    Defaults to the last 30 days if dates are unsupplied.
    """
    if not access_token:
        return {"error": "Missing access token"}, 400

    now = datetime.now(timezone.utc)
    if not start_date:
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = now.strftime("%Y-%m-%d")

    try:
        req = TransactionsGetRequest(
            access_token=access_token,
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
        )
        response = plaid_client.transactions_get(req)

        transactions = [txn.to_dict() for txn in response.transactions]
        return {"transactions": transactions}
    except ApiException as e:
        return {"error": _parse_api_error(e)}, 500
    except Exception as e:
        return {"error": str(e)}, 500


# -----------------------------------------------------------------------------
# Exchange Public Token
# -----------------------------------------------------------------------------
def exchange_public_token(
    public_token: str,
    user_id: Union[str, None] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Exchanges a public token for an access token and item ID."""
    if not public_token:
        return {"error": "Missing public token"}, 400

    try:
        req = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = plaid_client.item_public_token_exchange(req)
        if hasattr(response, "to_dict"):
            return cast(Dict[str, Any], response.to_dict())
        return dict(response)
    except ApiException as e:
        return {"error": _parse_api_error(e)}, 500
    except Exception as e:
        return {"error": str(e)}, 500