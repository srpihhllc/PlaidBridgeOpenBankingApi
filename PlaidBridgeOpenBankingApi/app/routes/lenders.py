# app/routes/lenders.py

from datetime import datetime

from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.lender import Lender  # ✅ Actual model that exists
from app.services.lender_verifier import verify_credentials

lenders_bp = Blueprint("lender", __name__)


# ---------- Lender Identity Verification ----------
@lenders_bp.route("/api/lender/verify", methods=["POST"])
@jwt_required()
def verify_lender_identity():
    data = request.get_json()
    required_fields = [
        "business_name",
        "owner_name",
        "ssn_or_ein",
        "address",
        "license_number",
    ]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required credentials"}), 400

    result = verify_credentials(data)
    status = "verified" if result["score"] > 80 and result["is_valid"] else "rejected"

    # Update lender status directly (mock flow)
    lender = Lender.query.filter_by(
        business_name=data["business_name"], owner_name=data["owner_name"]
    ).first()

    if lender:
        lender.verification_status = status
        lender.verification_score = result["score"]
        db.session.commit()

    return jsonify({"status": status, "details": result}), 200


# ---------- Bank Link Request ----------
@lenders_bp.route("/api/lender/link_bank_account", methods=["POST"])
@jwt_required()
def link_bank_account():
    data = request.get_json()
    lender_id = data.get("lender_id")
    institution = data.get("institution")
    plaid_token = data.get("access_token")

    if not all([lender_id, institution, plaid_token]):
        abort(400, description="Missing bank linking credentials")

    lender = Lender.query.get_or_404(lender_id)
    if lender.verification_status != "verified":
        abort(403, description="Lender not verified — cannot link bank account")

    lender.bank_linked = True
    lender.institution_name = institution
    lender.linked_at = datetime.utcnow()
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Bank account linked",
                "institution": institution,
                "timestamp": lender.linked_at.isoformat(),
            }
        ),
        200,
    )
