# --------------------------------------------
# Initialization File for Flask App
# --------------------------------------------

from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from dotenv import load_dotenv
import os

# --------------------------------------------
# Load environment variables
# --------------------------------------------
load_dotenv()

# --------------------------------------------
# Flask App Initialization
# --------------------------------------------
app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 86400

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
socketio = SocketIO(app)
CORS(app)
limiter = Limiter(app, default_limits=["200 per day", "50 per hour"])

# --------------------------------------------
# Import Routes
# --------------------------------------------
from . import routes  # Ensure you have a routes.py file

# --------------------------------------------
# Run App
# --------------------------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)


