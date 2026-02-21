# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/pulse_routes.py


from flask import Blueprint, jsonify, make_response

pulse_bp = Blueprint("pulse", __name__, url_prefix="/pulse")


@pulse_bp.route("/vault/<int:vault_id>", methods=["GET"])
def vault_pulse(vault_id):
    payload = {"vault_id": vault_id, "status": "ok", "data": None}
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "public, max-age=5"
    return resp


@pulse_bp.route("/access_token/<int:token_id>", methods=["GET"])
def access_token_pulse(token_id):
    payload = {"token_id": token_id, "status": "ok", "data": None}
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "public, max-age=5"
    return resp
