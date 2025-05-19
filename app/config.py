# app/config.py
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # API Keys / Secrets
    API_KEY = os.getenv('API_KEY')
    API_SECRET = os.getenv('API_SECRET')
    ACCOUNT_NUMBER = os.getenv('ACCOUNT_NUMBER')
    PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
    PLAID_SECRET = os.getenv('PLAID_SECRET')
    PLAID_PUBLIC_KEY = os.getenv('PLAID_PUBLIC_KEY')
    
    # Flask / SQLAlchemy Settings
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'supersecretkey')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
    
    # Application Settings
    PORT = int(os.getenv('PORT', 3000))
