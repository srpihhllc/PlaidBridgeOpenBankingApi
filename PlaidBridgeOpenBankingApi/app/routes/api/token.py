# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/api/token.py

from flask import Blueprint, jsonify

from app.extensions import db
from app.models.access_token import AccessToken

bp = Blueprint("token_api", __name__)


@bp.route("/api/token/revoke/<token_id>", methods=["POST"])
def revoke_token(token_id):
    token = AccessToken.query.filter_by(token=token_id).first()
    if not token:
        return jsonify({"error": "Token not found"}), 404

    db.session.delete(token)
    db.session.commit()
    return jsonify({"status": "revoked"})
