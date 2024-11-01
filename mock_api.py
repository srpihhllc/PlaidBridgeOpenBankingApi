from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Mock endpoint to simulate API response
@app.route('/mock-endpoint', methods=['POST'])
def mock_endpoint():
    data = request.get_json()
    # Mock response logic here
    response = {
        'accountNumber': '7030 3429 9651',
        'routingNumber': '026 015 053',
        'accountName': 'Found Bank Account'
    }
    return jsonify(response), 200

# Secure endpoint to access only statements
@app.route('/statements', methods=['GET'])
def get_statements():
    # Simulated statement data
    statements = [
        {'date': '2024-01-01', 'description': 'Deposit', 'amount': '500.00'},
        {'date': '2024-02-01', 'description': 'Withdrawal', 'amount': '-200.00'}
    ]
    return jsonify(statements), 200

# Access control - prevent access to other routes
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    return jsonify({'message': 'Access Denied'}), 403

# Endpoint for manual login with username and password
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if username == os.getenv('MOCK_USERNAME') and password == os.getenv('MOCK_PASSWORD'):
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'message': 'Invalid credentials'}), 403

if __name__ == '__main__':
    app.run(port=5000)

