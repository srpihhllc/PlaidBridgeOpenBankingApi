from flask import Flask, request, jsonify
import requests
import os
import pay.plaidbridgeopenbankingapi  # Ensure this module is installed

app = Flask(__name__)

# Plaid API credentials
client_id = os.getenv("PLAID_CLIENT_ID")
secret = os.getenv("PLAID_SECRET")

# Create Link token
@app.route("/create_link_token", methods=["POST"])
def create_link_token():
    headers = {"Content-Type": "application/json"}
    data = {
        "client_id": client_id,
        "secret": secret,
        "user": {"client_user_id": "unique_user_id"},
        "client_name": "Plaid Test App",
        "products": ["auth"],
        "country_codes": ["US"],
        "language": "en"
    }
    response = requests.post("https://sandbox.plaid.com/link/token/create", headers=headers, json=data)
    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({"error": response.json()}), response.status_code

# Create payment
@app.route("/create_payment", methods=["POST"])
def create_payment():
    access_token = request.json.get("access_token")
    amount = request.json.get("amount")
    account_id = request.json.get("account_id")
    recipient_id = request.json.get("recipient_id")
    
    headers = {"Content-Type": "application/json"}
    data = {
        "access_token": access_token,
        "amount": {"currency": "USD", "value": amount},
        "account_id": account_id,
        "recipient_id": recipient_id
    }
    response = requests.post("https://sandbox.plaid.com/payment_initiation/payment/create", headers=headers, json=data)
    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({"error": response.json()}), response.status_code

if __name__ == "__main__":
    app.run(debug=True)
