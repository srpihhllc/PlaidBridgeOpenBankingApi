# app/__init__.py
import logging
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Create extension instances (without app binding)
db = SQLAlchemy()
jwt = JWTManager()
socketio = SocketIO()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"],
                  storage_uri=os.getenv('REDIS_URL', "redis://localhost:6379"))

def create_app():
    app = Flask(__name__)
    
    # Load configuration from config.py
    from app.config import Config
    app.config.from_object(Config)
    
    # Initialize extensions with the app instance
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)
    
    # Configure Logging
    log_level = app.config.get('LOG_LEVEL', 'DEBUG')
    logging.basicConfig(level=getattr(logging, log_level),
                        format="%(asctime)s [%(levelname)s] %(message)s")
    
    # Register routes/blueprints
    from app import routes  # This file should contain your route declarations
    app.register_blueprint(routes.bp)  # Assuming you have defined a blueprint 'bp' in routes.py
    
    return app
