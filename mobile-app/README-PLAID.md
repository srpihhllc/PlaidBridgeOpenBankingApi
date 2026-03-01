# Plaid Link (mobile) — Local dev guide

This document explains how to run the mobile app (Expo) and connect Plaid Link via your local Flask backend.

Prerequisites
- Backend running locally (Flask) with Plaid sandbox keys set in environment.
- ngrok (or publicly accessible backend) so mobile device / Expo can reach your backend.
- Expo CLI installed for mobile app.

1) Start your Flask backend
From the repo root (or the PlaidBridgeOpenBankingApi package):
```bash
# Create venv + install if you haven't
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate
pip install -r requirements.txt

# Ensure PLAID env vars are set (sandbox)
export PLAID_CLIENT_ID="your_plaid_client_id"
export PLAID_SECRET="your_plaid_secret"
export PLAID_ENV="sandbox"

# Run Flask (host on 0.0.0.0 so ngrok can forward)
export FLASK_APP=PlaidBridgeOpenBankingApi.app
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=5000
