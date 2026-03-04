# app/blueprints/subscriber_routes.py

"""
Subscriber profile routes.

Temporary POST endpoint /subscriber/update_profile to accept dashboard profile
updates. Logs posted keys, masks sensitive fields, persists a minimal safe
subset, and redirects back to the cockpit.

Replace with full validation, schema-aware mapping, CSRF-aware form handling,
and business-logic persistence as your permanent handler.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.extensions import db

subscriber_bp = Blueprint("subscriber", __name__, url_prefix="/subscriber")
logger = logging.getLogger(__name__)


@subscriber_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile() -> Any:
    """
    Temporary operator-facing handler for profile updates.

    Returns:
        A Flask redirect response to the subscriber dashboard or fallback routes.
    """

    # Convert ImmutableMultiDict -> plain dict
    form_data: dict[str, Any] = {k: v for k, v in request.form.items()}

    # Mask sensitive values for logs
    masked: dict[str, Any] = {}
    for k, v in form_data.items():
        try:
            lower = k.lower()
        except Exception:
            lower = k

        if any(s in lower for s in ("ssn", "password", "secret", "token")):
            masked[k] = "***REDACTED***"
        elif "email" in lower:
            parts = (v or "").split("@")
            masked[k] = (parts[0][:3] + "***@" + parts[1]) if len(parts) == 2 else "***REDACTED***"
        elif any(s in lower for s in ("phone", "tel")):
            masked[k] = f"****{(v or '')[-4:]}" if v else ""
        else:
            masked[k] = v

    # Operator log
    logger.info(
        "subscriber.update_profile (stub) called by user=%s; keys=%s; sample_masked=%s",
        getattr(current_user, "id", "anon"),
        list(form_data.keys()),
        {k: masked[k] for k in list(masked)[:8]},
    )

    # --- Minimal safe persistence ---
    persisted: list[str] = []
    try:
        changed = False

        if "first_name" in form_data:
            try:
                current_user.first_name = form_data.get("first_name") or getattr(
                    current_user, "first_name", None
                )
                persisted.append("first_name")
                changed = True
            except Exception:
                logger.debug("Could not set first_name on user model", exc_info=True)

        if "last_name" in form_data:
            try:
                current_user.last_name = form_data.get("last_name") or getattr(
                    current_user, "last_name", None
                )
                persisted.append("last_name")
                changed = True
            except Exception:
                logger.debug("Could not set last_name on user model", exc_info=True)

        if "primary_phone" in form_data:
            try:
                current_user.primary_phone = form_data.get("primary_phone") or getattr(
                    current_user, "primary_phone", None
                )
                persisted.append("primary_phone")
                changed = True
            except Exception:
                logger.debug("Could not set primary_phone on user model", exc_info=True)

        if "business_phone" in form_data:
            try:
                current_user.business_phone = form_data.get("business_phone")
                persisted.append("business_phone")
                changed = True
            except Exception:
                logger.debug(
                    "Could not set business_phone attribute on user model",
                    exc_info=True,
                )

        if changed:
            db.session.add(current_user)
            db.session.commit()
            logger.info(
                "subscriber.update_profile (stub) persisted fields=%s for user=%s",
                persisted,
                (
                    current_user.get_id()
                    if hasattr(current_user, "get_id")
                    else getattr(current_user, "id", "unknown")
                ),
            )

    except Exception:
        db.session.rollback()
        logger.exception(
            "subscriber.update_profile (stub) failed to persist minimal fields for user=%s",
            getattr(current_user, "id", "unknown"),
        )

    # Flash feedback
    if persisted:
        flash(
            "Profile updated (temporary handler). Please verify fields on your dashboard.",
            "success",
        )
    else:
        flash(
            "Profile update received (temporary). If nothing changed, check server "
            "logs for posted keys.",
            "info",
        )

    # --- Redirect back to subscriber dashboard ---
    try:
        return redirect(url_for("main.dashboard"))
    except Exception:
        try:
            return redirect(url_for("sub_ui.sub_index"))
        except Exception:
            logger.debug(
                "Fallback redirects missing: main.dashboard and sub_ui.sub_index",
                exc_info=True,
            )
            return redirect("/")
