# =============================================================================
# FILE: app/blueprints/subscriber_routes.py
# DESCRIPTION: Subscriber profile and API/UI endpoint handlers.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import jwt_required
from flask_login import current_user, login_required

from app.extensions import csrf, db

subscriber_bp = Blueprint("subscriber", __name__, url_prefix="/subscriber")
logger = logging.getLogger(__name__)

SUPPORTED_FIELDS = (
    "first_name",
    "last_name",
    "primary_phone",
    "business_phone",
)

SENSITIVE_FIELD_PARTS = (
    "ssn",
    "password",
    "secret",
    "token",
    "routing",
    "account",
)


def _mask_form_data(form_data: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}

    for key, value in form_data.items():
        lower_key = str(key).lower()
        string_value = "" if value is None else str(value)

        if any(part in lower_key for part in SENSITIVE_FIELD_PARTS):
            masked[key] = "***REDACTED***"
        elif "email" in lower_key:
            parts = string_value.split("@", 1)
            if len(parts) == 2:
                masked[key] = f"{parts[0][:3]}***@{parts[1]}"
            else:
                masked[key] = "***REDACTED***"
        elif "phone" in lower_key or "tel" in lower_key:
            masked[key] = (
                f"****{string_value[-4:]}" if string_value else ""
            )
        else:
            masked[key] = value

    return masked


# =============================================================================
# 1. SUBSCRIBER API ALIASES & PULSE ENDPOINTS
# =============================================================================

@subscriber_bp.route("/token-pulse", methods=["GET"])
@subscriber_bp.route("/api/subscriber/token-pulse", methods=["GET"])
@jwt_required(optional=True)
def subscriber_token_pulse():
    return jsonify({"status": "ok", "token_status": "active"}), 200


@subscriber_bp.route("/vault-activity", methods=["GET"])
@subscriber_bp.route("/api/subscriber/vault-activity", methods=["GET"])
@jwt_required(optional=True)
def subscriber_vault_activity():
    return jsonify({"status": "ok", "activity": []}), 200


# =============================================================================
# 2. SUBSCRIBER UI ENDPOINTS
# =============================================================================

@subscriber_bp.route("/fraud", methods=["GET"])
@login_required
def subscriber_fraud():
    return render_template("sub/fraud_drilldown.html")


@subscriber_bp.route("/settings/security", methods=["GET"])
@login_required
def subscriber_security_settings():
    return render_template("sub/settings.html")


@subscriber_bp.route("/api-key/regenerate", methods=["POST"])
@csrf.exempt
@login_required
def subscriber_regenerate_api_key():
    return jsonify({"status": "ok", "api_key": "new_key_generated"}), 200


# =============================================================================
# 3. PROFILE MANAGEMENT
# =============================================================================

@subscriber_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile() -> Any:
    form_data: dict[str, Any] = {
        key: value for key, value in request.form.items()
    }

    user_id = getattr(current_user, "id", None)

    logger.info(
        "subscriber.update_profile called: user_id=%r authenticated=%r "
        "keys=%s masked_data=%s",
        user_id,
        current_user.is_authenticated,
        list(form_data.keys()),
        _mask_form_data(form_data),
    )

    persisted: list[str] = []

    try:
        for field_name in SUPPORTED_FIELDS:
            if field_name not in form_data:
                continue

            value = (form_data.get(field_name) or "").strip()

            if not hasattr(current_user, field_name):
                raise AttributeError(
                    f"User model {type(current_user).__name__!r} does not "
                    f"define supported field {field_name!r}"
                )

            setattr(current_user, field_name, value)
            persisted.append(field_name)

        if persisted:
            db.session.add(current_user)
            db.session.commit()

            logger.info(
                "subscriber.update_profile committed fields=%s user_id=%r",
                persisted,
                user_id,
            )
        else:
            logger.info(
                "subscriber.update_profile received no supported fields "
                "for user_id=%r",
                user_id,
            )

    except Exception:
        db.session.rollback()
        logger.exception(
            "subscriber.update_profile failed for user_id=%r",
            user_id,
        )
        raise

    if persisted:
        flash("Profile updated successfully.", "success")
    else:
        flash("No supported profile fields were changed.", "info")

    return redirect(url_for("main.dashboard"))