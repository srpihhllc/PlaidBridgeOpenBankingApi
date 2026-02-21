# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/letter_routes.py

from flask import Blueprint, current_app, jsonify, make_response, request
from flask_jwt_extended import jwt_required

from app.services.letter_renderer import render_letter
from app.services.pdf_generator import render_pdf_from_markdown

letter_bp = Blueprint("letters", __name__)


@letter_bp.route("/generate_letter/<template_name>", methods=["POST"])
@jwt_required()
def generate_letter(template_name):
    try:
        context = request.get_json()
        letter = render_letter(f"{template_name}.md", context)
        return jsonify({"letter": letter}), 200
    except Exception as e:
        current_app.logger.exception("Letter generation failed")
        return jsonify({"error": str(e)}), 500


@letter_bp.route("/generate_letter_pdf/<template_name>", methods=["POST"])
@jwt_required()
def generate_letter_pdf(template_name):
    try:
        context = request.get_json()
        markdown_text = render_letter(f"{template_name}.md", context)
        pdf_data = render_pdf_from_markdown(markdown_text)

        response = make_response(pdf_data)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"attachment; filename={template_name}.pdf"
        return response

    except Exception as e:
        current_app.logger.exception("PDF generation failed")
        return jsonify({"error": str(e)}), 500
