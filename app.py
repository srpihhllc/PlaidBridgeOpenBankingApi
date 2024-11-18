from flask import Flask, render_template, request, jsonify
import plaid
import os

app = Flask(__name__)

# Initialize the Plaid client
client = plaid.Client(client_id=os.getenv('PLAID_CLIENT_ID'),
                      secret=os.getenv('PLAID_SECRET'),
                      environment=os.getenv('PLAID_ENV', 'sandbox'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_link_token', methods=['POST'])
def create_link_token():
    try:
        response = client.LinkToken.create({
            'user': {
                'client_user_id': 'unique_user_id'
            },
            'client_name': 'PlaidBridgeOpenBankingAPI',
            'products': ['auth'],
            'country_codes': ['US'],
            'language': 'en'
        })
        return jsonify(response)
    except plaid.errors.PlaidError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/exchange_public_token', methods=['POST'])
def exchange_public_token():
    try:
        public_token = request.json['public_token']
        response = client.Item.public_token.exchange(public_token)
        access_token = response['access_token']
        return jsonify({'access_token': access_token})
    except plaid.errors.PlaidError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/accounts', methods=['POST'])
def get_accounts():
    try:
        access_token = request.json['access_token']
        response = client.Accounts.get(access_token)
        return jsonify(response)
    except plaid.errors.PlaidError as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
      
