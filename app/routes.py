# app/routes.py
from flask import Blueprint, jsonify

# Create a blueprint for your routes
bp = Blueprint('api', __name__)

@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# Add more endpoints here as you continue to modularize your routes.
