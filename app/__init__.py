# app/__init__.py

import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize Flask app
app = Flask(__name__)

# ✅ Configuration settings
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mock_api.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'supersecretkey')

# ✅ Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# ✅ Flask-Limiter for rate limiting (using memory storage, no Redis)
from limits.storage import MemoryStorage
limiter = Limiter(app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"], storage_uri="memory://")

# ✅ Configure Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format="%(asctime)s [%(levelname)s] %(message)s")

# ✅ Create App Factory Function
def create_app():
    app = Flask(__name__)

    # Load configuration from config.py
    from app.config import Config
    app.config.from_object(Config)

    # Initialize extensions with the app instance
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    # Register routes/blueprints
    from app import routes  # Ensure routes.py defines 'bp'
    app.register_blueprint(routes.bp)

    return app
