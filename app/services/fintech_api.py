# =============================================================================
# FILE: app/services/fintech_api.py
# DESCRIPTION: Service layer for non-Plaid FinTech integrations (TrueLayer, Tink)
#              Primarily used for secondary lender/account verification checks.
# =============================================================================
import logging
import os

import requests

logger = logging.getLogger(__name__)

# NOTE: In a production environment, base URLs and API keys would be loaded
# from app.config or environment variables and passed securely.
TRUELAYER_BASE_URL = os.getenv("TRUELAYER_API_URL", "https://api.truelayer.com")
TINK_BASE_URL = os.getenv("TINK_API_URL", "https://api.tink.com")

# ---------------------------
# Fintech Account Verification API
# ---------------------------


def _make_fintech_verification_request(vendor_name: str, url: str, account_data: dict) -> dict:
    """Generic helper to handle external verification API calls."""
    logger.info(f"Attempting verification via {vendor_name} to URL: {url}")

    # NOTE: You must include proper authentication headers (e.g., Bearer Token)
    # in a real application, which should be retrieved from configuration.
    headers = {
        "Content-Type": "application/json",
        # 'Authorization': f"Bearer {os.getenv(f'{vendor_name.upper()}_API_KEY')}" # Example
    }

    try:
        response = requests.post(
            url,
            json=account_data,
            headers=headers,
            timeout=10,  # Set a reasonable timeout
        )
        response.raise_for_status()  # Raise exception for bad status codes (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        error_message = f"❌ {vendor_name} verification request failed: {e}"
        logger.error(error_message, exc_info=True)
        # Log the response body if available for debugging
        try:
            if response is not None:
                logger.debug(f"{vendor_name} Error Response Body: {response.text}")
        except NameError:
            pass  # response object not yet defined

        return {"error": error_message}
    except Exception as e:
        error_message = f"❌ An unexpected error occurred during {vendor_name} verification: {e}"
        logger.critical(error_message, exc_info=True)
        return {"error": error_message}


def verify_via_truelayer(account_data: dict) -> dict:
    """Verifies lender account credentials via TrueLayer API."""
    return _make_fintech_verification_request(
        "TrueLayer", f"{TRUELAYER_BASE_URL}/verify", account_data
    )


def verify_via_tink(account_data: dict) -> dict:
    """Verifies lender account credentials via Tink API."""
    return _make_fintech_verification_request("Tink", f"{TINK_BASE_URL}/verify", account_data)
