#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/api.py

from flask import Blueprint, jsonify



api_bp = Blueprint("api", __name__, url_prefix="/api/v1")



@api_bp.route("/health", methods=["GET"])

def health_check():

    """API healthcheck endpoint."""

    return jsonify({"status": "healthy", "service": "PlaidBridgeOpenBankingApi"}), 200

