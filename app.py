# app.py

from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, abort, render_template
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import os
import csv
import pdfplumber
import logging
from werkzeug.utils import secure_filename
from fpdf import FPDF
from plaid.api import plaid_api
from plaid.model import *
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from datetime import datetime, timedelta
from pymongo import MongoClient
import requests

from .example_module import ExampleClass  # Ensure this path is correct

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')
socketio = SocketIO(app)

# Get the PORT from environment variables
port = int(os.getenv("PORT", 3000))

# Ensure the statements directory exists
app.config['UPLOAD_FOLDER'] = 'statements'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit file size to 16MB
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Global variable for account balance
account_balance = 848583.68

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Starting application")

# Plaid API configuration
configuration = Configuration(
    host="https://sandbox.plaid.com",
    api_key={
        'clientId': os.getenv('PLAID_CLIENT_ID'),
        'secret': os.getenv('PLAID_SECRET')
    }
)
api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)

# Treasury Prime API configuration
treasury_prime_env = os.getenv('TREASURY_PRIME_ENV', 'sandbox')
if treasury_prime_env == 'production':
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_PRODUCTION_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_PRODUCTION_API_URL')
else:
    TREASURY_PRIME_API_KEY = os.getenv('TREASURY_PRIME_SANDBOX_API_KEY')
    TREASURY_PRIME_API_URL = os.getenv('TREASURY_PRIME_SANDBOX_API_URL')

if TREASURY_PRIME_API_URL is None:
    raise ValueError("TREASURY_PRIME_API_URL is not set in the environment variables.")

# MongoDB configuration
mongo_client = MongoClient(os.getenv('COSMOS_DB_CONNECTION_STRING'))
db = mongo_client['plaidbridgeopenbankingapi-database']
todos_collection = db['todos']

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        user = User(user_id)
        login_user(user)
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

# Additional routes and functionalities go here...

if __name__ == "__main__":
    if os.getenv('FLASK_ENV') == 'production':
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    else:
        socketio.run(app, host="0.0.0.0", port=port)

       
        

                
  
       


        

        
    
       


