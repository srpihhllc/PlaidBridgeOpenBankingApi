# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/grants_routes.py

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services.grant_writer import compose_grant

grants_bp = Blueprint("grants", __name__, url_prefix="/api/grants")


@grants_bp.route("/compose/<grant_type>", methods=["POST"])
@jwt_required()
def compose_grant_endpoint(grant_type):
    try:
        payload = request.get_json()
        narrative = compose_grant(grant_type, payload)
        return jsonify({"narrative": narrative}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
