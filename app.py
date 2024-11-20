from flask import Flask, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

# Configuration
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_BASE_URL = "https://sandbox.plaid.com"

# Logging
logging.basicConfig(level=logging.DEBUG)

# Debug route to verify environment variables
@app.route("/debug_env", methods=["GET"])
def debug_env():
    return jsonify({
        "PLAID_CLIENT_ID": PLAID_CLIENT_ID,
        "PLAID_SECRET": PLAID_SECRET
    })

# Create Link token
@app.route("/create_link_token", methods=["POST"])
def create_link_token():
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
        logging.error(e)
        return jsonify({"error": str(e)}), 500

# Create payment
@app.route("/create_payment", methods=["POST"])
def create_payment():
    try:
        access_token = request.json.get("access_token")
        amount = request.json.get("amount")
        account_id = request.json.get("account_id")
        recipient_id = request.json.get("recipient_id")

        headers = {"Content-Type": "application/json"}
        data = {
            "access_token": access_token,
            "amount": {"currency": "USD", "value": amount},
            "ach_class": "ppd",
            "account_id": account_id,
            "recipient_id": recipient_id
        }
        response = requests.post(f"{PLAID_BASE_URL}/payment_initiation/payment/create", headers=headers, json=data)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logging.error(e)
        return jsonify({"error": str(e)}), 500

# Simple Hello World route
@app.route('/')
def hello():
    return 'Hello, World!'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
          
       
      
