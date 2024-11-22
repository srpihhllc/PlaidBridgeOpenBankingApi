import requests
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constant values
BASE_URL_SANDBOX = "https://sandbox.plaid.com"

class PlaidBridgeOpenBankingAPI:
    def __init__(self, base_url: str, client_id: str, secret: str):
        self.base_url = base_url
        self.client_id = client_id
        self.secret = secret

    def process_payment(self, payment_data: dict) -> dict:
        """
        Process payment using Plaid API.

        Args:
            payment_data: Payment data containing:
                - recipient_id
                - reference
                - amount (currency and value)

        Returns:
            Payment response from Plaid API.

        Raises:
            ValueError: If payment_data is invalid.
            requests.RequestException: If API request fails.
        """
        # Validate payment_data
        required_keys = ["recipient_id", "reference", "amount"]
        if not all(key in payment_data for key in required_keys):
            raise ValueError("Invalid payment_data")

        # Set API endpoint and headers
        endpoint = f"{self.base_url}/payment_initiation/payment"
        headers = {
            "Content-Type": "application/json",
            "Client-ID": self.client_id,
            "Secret": self.secret
        }

        # Prepare payment request data
        payment_request = {
            "recipient_id": payment_data["recipient_id"],
            "reference": payment_data["reference"],
            "amount": {
                "currency": payment_data["amount"]["currency"],
                "value": payment_data["amount"]["value"]
            }
        }

        # Send payment request to Plaid API
        try:
            response = requests.post(endpoint, headers=headers, json=payment_request)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise Exception(f"Payment processing failed: {e}")
        except requests.RequestException as e:
            logger.error(f"Request exception occurred: {e}")
            raise Exception(f"Payment processing failed: {e}")

# Initialize PlaidBridgeOpenBankingAPI instance
def get_plaid_bridge_api():
    base_url = BASE_URL_SANDBOX  # Update to production URL when ready
    client_id = os.getenv("PLAID_CLIENT_ID")
    secret = os.getenv("PLAID_SECRET")

    if not client_id or not secret:
        raise ValueError("PLAID_CLIENT_ID and PLAID_SECRET must be set in environment variables")

    return PlaidBridgeOpenBankingAPI(base_url, client_id, secret)
        

