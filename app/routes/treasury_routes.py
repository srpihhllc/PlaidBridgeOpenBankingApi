import logging
from functools import wraps

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_login import current_user

from app.extensions import csrf
from app.services.card_manager import suspend_card, unfreeze_card

# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/treasury_routes.py


logger = logging.getLogger(__name__)


treasury_bp = Blueprint("treasury_bp", __name__)
csrf.exempt(treasury_bp)


def _require_card_operator_or_auth(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if current_app.config.get("TESTING"):

            return fn(*args, **kwargs)

        verify_jwt_in_request(optional=True)

        if get_jwt_identity() is not None or getattr(
            current_user, "is_authenticated", False
        ):

            return fn(*args, **kwargs)

        return jsonify({"status": "error", "message": "Authentication required."}), 401

    return wrapper


@treasury_bp.route("/cards/<card_id>/suspend", methods=["POST"])
@_require_card_operator_or_auth
def suspend_card_route(card_id: str):
    """Suspend a Treasury Prime card."""

    try:

        success = suspend_card(card_id)

        if success:

            return (
                jsonify({"status": "success", "message": f"Card {card_id} suspended."}),
                200,
            )

        return (
            jsonify(
                {"status": "error", "message": f"Failed to suspend card {card_id}."}
            ),
            400,
        )

    except Exception as err:

        logger.exception("Error suspending card %s", card_id)

        return jsonify({"status": "error", "message": str(err)}), 500


@treasury_bp.route("/cards/<card_id>/unfreeze", methods=["POST"])
@_require_card_operator_or_auth
def unfreeze_card_route(card_id: str):
    """Unfreeze a Treasury Prime card."""

    try:

        success = unfreeze_card(card_id)

        if success:

            return (
                jsonify({"status": "success", "message": f"Card {card_id} unfrozen."}),
                200,
            )

        return (
            jsonify(
                {"status": "error", "message": f"Failed to unfreeze card {card_id}."}
            ),
            400,
        )

    except Exception as err:

        logger.exception("Error unfreezing card %s", card_id)

        return jsonify({"status": "error", "message": str(err)}), 500
