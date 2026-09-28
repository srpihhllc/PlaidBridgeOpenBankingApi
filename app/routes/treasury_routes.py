#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/treasury_routes.py

import logging
from flask import Blueprint, jsonify
from app.services.card_manager import suspend_card, unfreeze_card

logger = logging.getLogger(__name__)

treasury_bp = Blueprint("treasury_bp", __name__)

@treasury_bp.route("/cards/<card_id>/suspend", methods=["POST"])
def suspend_card_route(card_id: str):
    """Suspend a Treasury Prime card."""
    try:
        success = suspend_card(card_id)
        if success:
            return jsonify({"status": "success", "message": f"Card {card_id} suspended."}), 200
        return jsonify({"status": "error", "message": f"Failed to suspend card {card_id}."}), 400
    except Exception as err:
        logger.exception("Error suspending card %s", card_id)
        return jsonify({"status": "error", "message": str(err)}), 500

@treasury_bp.route("/cards/<card_id>/unfreeze", methods=["POST"])
def unfreeze_card_route(card_id: str):
    """Unfreeze a Treasury Prime card."""
    try:
        success = unfreeze_card(card_id)
        if success:
            return jsonify({"status": "success", "message": f"Card {card_id} unfrozen."}), 200
        return jsonify({"status": "error", "message": f"Failed to unfreeze card {card_id}."}), 400
    except Exception as err:
        logger.exception("Error unfreezing card %s", card_id)
        return jsonify({"status": "error", "message": str(err)}), 500