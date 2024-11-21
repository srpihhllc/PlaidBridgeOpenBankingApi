from flask import Flask, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

# Configuration
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_BASE_URL = "https://sandbox.plaid.com"
PORT = int(os.environ.get("PORT", 5000))

# Logging
logging.basicConfig(level=logging.DEBUG)

# Validate environment variables
if not PLAID_CLIENT_ID or not PLAID_SECRET:
    logging.error("PLAID_CLIENT_ID and PLAID_SECRET must be set")
    exit(1)

@app.route("/debug_env", methods=["GET"])
def debug_env() -> dict:
    """Verify environment variables."""
    return jsonify({
        "PLAID_CLIENT_ID": PLAID_CLIENT_ID,
        "PLAID_SECRET": "*****"
    })

@app.route("/create_link_token", methods=["POST"])
def create_link_token() -> dict:
    """Create Plaid link token."""
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "client_id": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "user": {"client_user_id": "unique_user_id"},
            "client_name": "Plaid Test App",
            "products": ["auth"],
            "country_codes": ["US"],
            "language": "en"
        }
        response = requests.post(f"{PLAID_BASE_URL}/link/token/create", headers=headers, json=data)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(f"Error creating link token: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/create_payment", methods=["POST"])
def create_payment() -> dict:
    """Create payment."""
    try:
        data = request.json
        required_fields = ["access_token", "amount", "account_id", "recipient_id"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required parameters"}), 400

        headers = {"Content-Type": "application/json"}
        response = requests.post(f"{PLAID_BASE_URL}/payment_initiation/payment/create", headers=headers, json=data)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(f"Error creating payment: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/')
def hello() -> str:
    """Simple Hello World route."""
    return 'Hello, World!'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
       
      
