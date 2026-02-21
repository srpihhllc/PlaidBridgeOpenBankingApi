# =============================================================================
# FILE: app/blueprints/cfpb_routes.py
# DESCRIPTION: Routes for handling CFPB-related API requests.
# =============================================================================

import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import ComplaintLog
from app.services.letter_renderer import render_letter
from app.services.pdf_generator import render_pdf_from_markdown
from app.utils.redis_utils import get_redis_client

cfpb_bp = Blueprint("cfpb", __name__)


# ----------------------------------------
# 1. Complaint PDF Generator
# ----------------------------------------
@cfpb_bp.route("/generate_cfpb_complaint/<template_name>", methods=["POST"])
@jwt_required()
def generate_cfpb_pdf(template_name):
    try:
        context = request.get_json()
        markdown_text = render_letter(f"{template_name}.md", context)
        pdf = render_pdf_from_markdown(markdown_text)

        return (
            jsonify(
                {
                    "message": "Complaint generated",
                    "pdf_size_bytes": len(pdf),
                    "pdf_base64": pdf.decode("utf-8"),
                }
            ),
            200,
        )
    except FileNotFoundError:
        current_app.logger.error(f"Template not found: {template_name}.md")
        return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        current_app.logger.error(f"An error occurred while generating PDF: {e}")
        return jsonify({"error": "Failed to generate PDF"}), 500


# ----------------------------------------
# 2. Complaint Submission & Logging
# ----------------------------------------
@cfpb_bp.route("/api/cfpb/complaint", methods=["POST"])
def submit_complaint():
    """
    Submits a user complaint to the CFPB system.
    This is a mock endpoint for demonstration purposes.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    required_fields = ["description", "user_id"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    # Log the complaint to the database
    try:
        cfpb_payload = {
            "description": data["description"],
            "user_id": data["user_id"],
            "product": data.get("product", "Unspecified"),
            "issue": data.get("issue", "General"),
            "company": data.get("company", "PlaidBridge"),
            "submitted_at": datetime.utcnow().isoformat(),
        }

        # Log to Redis for real-time monitoring
        redis_client = get_redis_client()
        if redis_client:
            redis_client.lpush("cfpb:complaints", json.dumps(cfpb_payload))

        # Log to the database for persistence
        db.session.add(
            ComplaintLog(
                user_id=data["user_id"],
                payload=json.dumps(cfpb_payload),
                status="submitted",
            )
        )
        db.session.commit()

        return jsonify({"message": "Complaint submitted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error submitting CFPB complaint: {e}")
        return jsonify({"error": "Internal server error"}), 500
