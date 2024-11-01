from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)
limiter = Limiter(app, key_func=get_remote_address)

logging.basicConfig(level=logging.INFO)

# Dummy data for illustration
def manual_login_and_link_bank_account():
    logging.info("Manual login and account linking process initiated.")
    # Simulate your actual logic here
    return {"message": "Manual login and bank account linking completed successfully.", "accessToken": "dummy-access-token"}

@app.route('/manual-login', methods=['POST'])
def manual_login():
    try:
        # Simulate logic for handling manual login
        result = manual_login_and_link_bank_account()
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error in manual login and bank account linking: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(port=3000)
