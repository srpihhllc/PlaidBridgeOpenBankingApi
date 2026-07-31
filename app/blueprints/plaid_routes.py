# =============================================================================
# FILE: app/blueprints/plaid_routes.py
# DESCRIPTION: Finalized Plaid token lifecycle handler with Fernet encryption
# =============================================================================

import os
from typing import Any
from cryptography.fernet import Fernet
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.plaid_item import PlaidItem
from app.models.trace_events import TraceEvent
from app.telemetry.ttl_emit import ttl_emit

plaid_bp = Blueprint("plaid", __name__)

class PlaidClientWithTimeout:
    """Recursive wrapper to ensure Plaid SDK calls never hang indefinitely."""
    def __init__(self, client, default_timeout=10):
        self._client = client
        self._default_timeout = default_timeout

    def __getattr__(self, name):
        original_attribute = getattr(self._client, name)
        if callable(original_attribute):
            def wrapper(*args, **kwargs):
                if "timeout" not in kwargs:
                    kwargs["timeout"] = self._default_timeout
                return original_attribute(*args, **kwargs)
            return wrapper
        return PlaidClientWithTimeout(original_attribute, self._default_timeout)

def _get_plaid_client_and_log_error() -> Any:
    """Lazily imports Plaid SDK and returns wrapped client."""
    try:
        from plaid import Client, environments
        plaid_env_str = current_app.config.get("PLAID_ENV", "Development")
        environment = getattr(environments, plaid_env_str.capitalize(), environments.Development)
        raw_client = Client(
            client_id=current_app.config["PLAID_CLIENT_ID"],
            secret=current_app.config["PLAID_SECRET"],
            environment=environment,
        )
        return PlaidClientWithTimeout(raw_client)
    except Exception as e:
        current_app.logger.error(f"Plaid SDK initialization failed: {e}")
        return None

@plaid_bp.route("/create_link_token", methods=["POST"])
@login_required
def create_link_token():
    """Creates a Link token for client-side integration."""
    plaid_client = _get_plaid_client_and_log_error()
    if not plaid_client:
        return jsonify({"error": "Service unavailable"}), 503

    try:
        response = plaid_client.LinkToken.create({
            "user": {"client_user_id": str(current_user.id)},
            "client_name": "Plaid Bridge",
            "products": ["auth", "transactions"],
            "country_codes": ["US"],
            "language": "en",
            "redirect_uri": current_app.config.get("PLAID_REDIRECT_URI", ""),
        })
        return jsonify({"link_token": response["link_token"]})
    except Exception as e:
        current_app.logger.error(f"Link Token creation error: {e}")
        return jsonify({"error": "Failed to generate link token"}), 500

@plaid_bp.route("/exchange_public_token", methods=["POST"])
@login_required
def exchange_public_token():
    """Exchanges public token, encrypts access token, and persists to DB."""
    public_token = request.json.get("public_token")
    if not public_token:
        return jsonify({"error": "Missing public token"}), 400

    plaid_client = _get_plaid_client_and_log_error()
    if not plaid_client:
        return jsonify({"error": "Service unavailable"}), 503

    try:
        # 1. Exchange Token
        exchange_response = plaid_client.Item.public_token_exchange(public_token)
        access_token = exchange_response["access_token"]
        item_id = exchange_response["item_id"]

        # 2. Check for existence
        if PlaidItem.query.filter_by(user_id=current_user.id, plaid_item_id=item_id).first():
            return jsonify({"success": True, "message": "Already linked"}), 200

        # 3. Secure Encryption
        encryption_key = os.getenv("PLAID_ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("PLAID_ENCRYPTION_KEY not set")
        
        f = Fernet(encryption_key.encode())
        encrypted_token = f.encrypt(access_token.encode()).decode('utf-8')

        # 4. Persistence
        new_item = PlaidItem(
            user_id=current_user.id,
            plaid_item_id=item_id,
            plaid_access_token=encrypted_token
        )
        db.session.add(new_item)
        db.session.commit()

        # 5. Telemetry Pulse
        ttl_emit(f"ttl:plaid:success:{current_user.id}", status="success", ttl=300)
        
        return jsonify({"success": True, "item_id": item_id})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Exchange error for user {current_user.id}: {e}")
        ttl_emit(f"ttl:plaid:error:{current_user.id}", status="error", ttl=300)
        return jsonify({"error": "Exchange failed"}), 500