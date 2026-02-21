# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/plaid_routes.py

import os
from typing import Any

from cryptography.fernet import Fernet  # Import the encryption library
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.extensions import db
from app.models.plaid_item import PlaidItem
from app.models.trace_events import TraceEvent

# CORRECT: Import models directly from their files

# NOTE: Plaid-specific imports are intentionally omitted from the top-level
# to prevent ModuleNotFoundError during Alembic migrations.

plaid_bp = Blueprint("plaid", __name__)


class PlaidClientWithTimeout:
    """
    A recursive wrapper for the Plaid Client that automatically applies a default
    timeout to every API call, including those on nested service objects.
    This ensures no request can hang indefinitely.
    """

    def __init__(self, client, default_timeout=10):
        # We store the original client instance and the default timeout.
        self._client = client
        self._default_timeout = default_timeout

    def __getattr__(self, name):
        """
        Intercepts attribute access to the wrapped Plaid client.
        - If the attribute is a callable method, it returns a new callable
          that applies the default timeout.
        - If the attribute is a nested object, it recursively wraps that
          object in a new PlaidClientWithTimeout instance.
        """
        # Get the original attribute from the underlying client object
        original_attribute = getattr(self._client, name)

        if callable(original_attribute):
            # If the attribute is a function (like `LinkToken.create`),
            # return a new function that injects the default timeout.
            def wrapper(*args, **kwargs):
                if "timeout" not in kwargs:
                    kwargs["timeout"] = self._default_timeout
                return original_attribute(*args, **kwargs)

            return wrapper
        else:
            # If the attribute is a nested service object (like `client.Item`),
            # recursively wrap it to ensure its methods also get a timeout.
            return PlaidClientWithTimeout(original_attribute, self._default_timeout)


def _get_plaid_client_and_log_error() -> Any:
    """
    Lazily imports and instantiates the Plaid client, and wraps it with the
    recursive timeout handler. Handles ImportError gracefully with telemetry.
    """
    try:
        from plaid import Client, environments

        # Determine Plaid environment from config.
        plaid_env_str = current_app.config.get("PLAID_ENV", "Development")
        environment = getattr(environments, plaid_env_str.capitalize(), environments.Development)

        raw_client = Client(
            client_id=current_app.config["PLAID_CLIENT_ID"],
            secret=current_app.config["PLAID_SECRET"],
            environment=environment,
        )
        return PlaidClientWithTimeout(raw_client)
    except ImportError as e:
        # Telemetry: Log the SDK import failure
        db.session.add(
            TraceEvent(
                event_type="PLAID_SDK_MISSING",
                ip=request.remote_addr,
                detail="Plaid SDK could not be imported. Is it installed?",
                meta=str(e)[:512],
            )
        )
        db.session.commit()
        return None


@plaid_bp.route("/create_link_token", methods=["POST"])
def create_link_token():
    """Creates a Link token for Plaid's client-side library."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401

    plaid_client = _get_plaid_client_and_log_error()
    if not plaid_client:
        return jsonify({"error": "Plaid service is temporarily unavailable."}), 503

    try:
        from plaid.errors import PlaidError as PlaidErrorType
    except Exception:
        PlaidErrorType = Exception

    try:
        # The timeout is now automatically applied by the recursive wrapper.
        response = plaid_client.LinkToken.create(
            {
                "user": {"client_user_id": str(current_user.id)},
                "client_name": "Plaid Bridge",
                "products": ["auth", "transactions"],
                "country_codes": ["US"],
                "language": "en",
                "redirect_uri": current_app.config.get("PLAID_REDIRECT_URI", ""),
                "link_customization_name": "default",
            }
        )

        db.session.add(
            TraceEvent(
                event_type="PLAID_LINK_TOKEN_CREATED",
                email=current_user.email,
                ip=request.remote_addr,
                detail="Plaid Link token created successfully.",
                meta={
                    "link_token_id": response["link_token"],
                    "request_id": response["request_id"],
                },
            )
        )
        db.session.commit()

        return jsonify({"link_token": response["link_token"]})
    except PlaidErrorType as e:
        meta = {
            "error_code": getattr(e, "code", None),
            "display_message": getattr(e, "display_message", None),
            "error_type": getattr(e, "error_type", None),
            "raw_error_message": str(e),
        }
        db.session.add(
            TraceEvent(
                event_type="PLAID_API_ERROR",
                email=current_user.email,
                ip=request.remote_addr,
                detail=f"Plaid API error: {meta.get('error_code')}",
                meta=meta,
            )
        )
        db.session.commit()
        return jsonify({"error": "Plaid API error."}), 500
    except Exception as e:
        db.session.add(
            TraceEvent(
                event_type="PLAID_LINK_TOKEN_ERROR",
                email=current_user.email,
                ip=request.remote_addr,
                detail="Failed to create Link token.",
                meta=str(e)[:512],
            )
        )
        db.session.commit()
        return jsonify({"error": "Failed to create Link token."}), 500


@plaid_bp.route("/exchange_public_token", methods=["POST"])
def exchange_public_token():
    """Exchanges a public token for an access token."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required."}), 401

    public_token = request.json.get("public_token")
    if not public_token:
        return jsonify({"error": "Missing public token"}), 400

    plaid_client = _get_plaid_client_and_log_error()
    if not plaid_client:
        return jsonify({"error": "Plaid service is temporarily unavailable."}), 503

    try:
        from plaid.errors import PlaidError as PlaidErrorType
    except Exception:
        PlaidErrorType = Exception

    try:
        # Timeout is now automatically applied by the recursive wrapper
        exchange_response = plaid_client.Item.public_token_exchange(public_token)
        access_token = exchange_response["access_token"]
        item_id = exchange_response["item_id"]

        # Timeout is handled for these nested calls as well
        item_response = plaid_client.Item.get(access_token)
        institution_id = item_response.get("item", {}).get("institution_id")

        institution_response = plaid_client.Institutions.get_by_id(institution_id)
        institution_name = institution_response.get("institution", {}).get("name")

        existing_item = PlaidItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
        if existing_item:
            db.session.add(
                TraceEvent(
                    event_type="PLAID_DUPLICATE_ITEM",
                    email=current_user.email,
                    ip=request.remote_addr,
                    detail="Attempted to exchange a public token for an existing item.",
                    meta={"item_id": item_id},
                )
            )
            db.session.commit()
            return jsonify({"success": True, "message": "Item already linked."})

        # --- SECRET ENCRYPTION LOGIC ---
        # NOTE: The encryption key should be a 32-URL-safe-base64-encoded bytes string.
        # It MUST be stored securely (e.g., in a secret manager or environment variable)
        # and not in the source code.
        encryption_key = os.getenv("PLAID_ENCRYPTION_KEY")
        if not encryption_key:
            return jsonify({"error": "Encryption key not found."}), 500

        f = Fernet(encryption_key.encode())
        encrypted_access_token = f.encrypt(access_token.encode())

        # Store the encrypted token in the database.
        # The PlaidItem.access_token field must be large enough to hold the
        # encrypted string (e.g., a Text field).
        plaid_item = PlaidItem(
            access_token=encrypted_access_token,
            item_id=item_id,
            user_id=current_user.id,
        )
        db.session.add(plaid_item)
        db.session.commit()
        # --- END ENCRYPTION LOGIC ---

        # Telemetry for successful exchange with enriched, masked data
        meta = {
            "item_id": item_id,
            "request_id": exchange_response["request_id"],
            "institution_id": institution_id,
            "institution_name": institution_name,
            # Masked for security: the original token is no longer available here.
            "access_token_masked": f"***{access_token[-4:]}",
        }
        db.session.add(
            TraceEvent(
                event_type="PLAID_TOKEN_EXCHANGED",
                email=current_user.email,
                ip=request.remote_addr,
                detail="Plaid public token exchanged successfully.",
                meta=meta,
            )
        )
        db.session.commit()

        return jsonify({"success": True})
    except PlaidErrorType as e:
        meta = {
            "error_code": getattr(e, "code", None),
            "display_message": getattr(e, "display_message", None),
            "error_type": getattr(e, "error_type", None),
            "raw_error_message": str(e),
        }
        db.session.add(
            TraceEvent(
                event_type="PLAID_API_ERROR",
                email=current_user.email,
                ip=request.remote_addr,
                detail=f"Plaid API error: {meta.get('error_code')}",
                meta=meta,
            )
        )
        db.session.commit()
        return jsonify({"error": "Plaid API error."}), 500
    except Exception as e:
        db.session.add(
            TraceEvent(
                event_type="PLAID_TOKEN_EXCHANGE_ERROR",
                email=current_user.email,
                ip=request.remote_addr,
                detail="Failed to exchange public token.",
                meta=str(e)[:512],
            )
        )
        db.session.commit()
        return jsonify({"error": "Failed to exchange public token."}), 500
