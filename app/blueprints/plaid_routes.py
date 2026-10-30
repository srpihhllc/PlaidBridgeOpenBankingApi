# =============================================================================
# FILE: app/blueprints/plaid_routes.py
# DESCRIPTION: Flask Blueprint HTTP endpoints for Plaid integrations.
# =============================================================================

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.plaid_item import PlaidItem
from app.services.plaid_api import get_plaid_client, get_transactions
from app.utils.plaid_crypto import encrypt_token
from app.utils.ttl_emit import ttl_emit

logger = logging.getLogger(__name__)

plaid_bp = Blueprint("plaid", __name__)


def _get_plaid_client_and_log_error() -> Any | None:
    """Return the configured Plaid SDK client, or None if initialization fails."""
    try:
        return get_plaid_client()
    except Exception:
        logger.exception("Unable to initialize Plaid client")
        return None


def _json_object() -> dict[str, Any]:
    """Return the request JSON object, or an empty dict for invalid/non-object JSON."""
    payload: object = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    return {}


def _response_value(result: object, key: str) -> Any:
    """Read a value from a mapping or an SDK response object."""
    if isinstance(result, Mapping):
        return result.get(key)
    return getattr(result, key, None)


@plaid_bp.route("/exchange_public_token", methods=["POST"])
@login_required
def exchange_public_token_route():
    """Exchange a Plaid public token for an encrypted access token."""
    payload = _json_object()
    public_token = payload.get("public_token")

    if not isinstance(public_token, str) or not public_token:
        return jsonify({"error": "public_token is required"}), 400

    plaid_client = _get_plaid_client_and_log_error()
    if plaid_client is None:
        return jsonify({"error": "Plaid client unavailable"}), 502

    try:
        result = plaid_client.Item.public_token_exchange(public_token)
        item_id = _response_value(result, "item_id")
        access_token = _response_value(result, "access_token")

        if not isinstance(item_id, str) or not isinstance(access_token, str):
            raise ValueError("Plaid token exchange returned an invalid response")

        item = PlaidItem(
            user_id=current_user.id,
            plaid_item_id=item_id,
            plaid_access_token=encrypt_token(access_token),
        )

        db.session.add(item)
        db.session.commit()

        ttl_emit(
            f"ttl:plaid:success:{current_user.id}",
            status="success",
            ttl=300,
        )

        return jsonify({"success": True, "item_id": item_id}), 200

    except Exception:
        db.session.rollback()
        logger.exception("Plaid public-token exchange failed")
        return jsonify({"error": "Plaid token exchange failed"}), 502


@plaid_bp.route("/create_link_token", methods=["POST"])
@login_required
def create_link_token_route():
    """Generate a Plaid Link token."""
    plaid_client = _get_plaid_client_and_log_error()
    if plaid_client is None:
        return jsonify({"error": "Service unavailable"}), 503

    try:
        result = plaid_client.LinkToken.create(
            user={"client_user_id": str(current_user.id)},
            client_name="PlaidBridge",
            products=["transactions"],
            country_codes=["US"],
            language="en",
        )

        link_token = _response_value(result, "link_token")
        if not isinstance(link_token, str) or not link_token:
            logger.error("Plaid Link token creation returned no link token")
            return jsonify({"error": "Plaid link token missing"}), 502

        ttl_emit(
            f"ttl:plaid:link_token:success:{current_user.id}",
            status="success",
            ttl=300,
        )

        return jsonify({"link_token": link_token}), 200

    except Exception:
        logger.exception("Plaid Link token creation failed")
        return jsonify({"error": "Plaid link token creation failed"}), 502


@plaid_bp.route("/transactions", methods=["POST"])
@login_required
def get_transactions_route():
    """Retrieve transactions using a Plaid access token."""
    payload = _json_object()

    access_token = payload.get("access_token")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")

    if not isinstance(access_token, str) or not access_token:
        return jsonify({"error": "access_token is required"}), 400

    if start_date is not None and not isinstance(start_date, str):
        return jsonify({"error": "start_date must be a string"}), 400

    if end_date is not None and not isinstance(end_date, str):
        return jsonify({"error": "end_date must be a string"}), 400

    try:
        result = get_transactions(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
        )

        if isinstance(result, tuple):
            body, status = result
            if status == 200:
                ttl_emit(
                    f"ttl:plaid:transactions:success:{current_user.id}",
                    status="success",
                    ttl=300,
                )
            return jsonify(body), status

        ttl_emit(
            f"ttl:plaid:transactions:success:{current_user.id}",
            status="success",
            ttl=300,
        )
        return jsonify(result), 200

    except Exception:
        logger.exception("Plaid transaction retrieval failed")
        return jsonify({"error": "Plaid transaction retrieval failed"}), 502