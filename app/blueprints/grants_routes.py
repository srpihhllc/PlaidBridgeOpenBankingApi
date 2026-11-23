# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/grants_routes.py



from flask import Blueprint, jsonify, request

from flask_jwt_extended import jwt_required



from app.services.grant_writer import compose_grant, prepare_grant



grants_bp = Blueprint("grants", __name__, url_prefix="/api/grants")





@grants_bp.route("/compose/<grant_type>", methods=["POST"])

@jwt_required()

def compose_grant_endpoint(grant_type):

    try:

        payload = dict(request.get_json(silent=True) or {})

        payload["grant_type"] = grant_type

        narrative = compose_grant(payload)

        return jsonify({"narrative": narrative}), 200

    except Exception as e:

        return jsonify({"error": str(e)}), 500





@grants_bp.route("/prepare/<grant_type>", methods=["POST"])

@jwt_required()

def prepare_grant_endpoint(grant_type):

    try:

        payload = dict(request.get_json(silent=True) or {})

        payload["grant_type"] = grant_type

        package = prepare_grant(payload)

        return jsonify(package), 200

    except Exception as e:

        return jsonify({"error": str(e)}), 500

