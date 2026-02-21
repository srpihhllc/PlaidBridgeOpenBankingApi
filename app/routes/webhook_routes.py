# app/routes/webhook_routes.py

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import CreditLedger

# Match the attribute name your registration expects
bp = Blueprint("webhook", __name__)


@bp.route("/webhook/treasury_events", methods=["POST"])
def treasury_events():
    event = request.get_json(silent=True) or {}
    if event.get("type") == "card.limit.updated":
        card_id = event.get("card_id")
        data = event.get("data", {})
        new_limit = data.get("new_limit")
        if card_id and new_limit is not None:
            ledger = CreditLedger.query.filter_by(card_id=card_id).first()
            if ledger:
                ledger.credit_limit = new_limit
                db.session.commit()
    return jsonify({"status": "received"}), 200


@bp.route("/webhook/card_update", methods=["POST"])
def handle_card_event():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")

    if user_id:
        from app.services.lending_cognition import CreditReflexManager

        violated = CreditReflexManager.detect_credit_violation(user_id)

        if violated:
            # TODO: auto-log to fraud_reports
            print(f"⚠️ Credit risk detected post-webhook for user {user_id}")

    return jsonify({"status": "processed"})
