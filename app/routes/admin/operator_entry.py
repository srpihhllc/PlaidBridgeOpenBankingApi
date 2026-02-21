# app/routes/admin/operator_entry.py
from datetime import datetime

import pyotp
from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FinancialAuditLog

admin = Blueprint("admin", __name__)

OPERATOR_IGNITION_CODE = "your-secure-ignition-code"  # move to env var


@admin.route("/operator-entry", methods=["POST"])
@login_required
def operator_entry():
    # 1. Validate ignition code
    passcode = request.form.get("passcode", "").strip()
    if passcode != OPERATOR_IGNITION_CODE:
        flash("Invalid operator ignition code.", "danger")
        _log_operator_event("operator_login_failed", "Invalid ignition code")
        return redirect(url_for("admin.operator_login"))

    # 2. Validate MFA (if enabled)
    if current_user.is_mfa_enabled:
        mfa_code = request.form.get("mfa_code", "").strip()
        totp = pyotp.TOTP(current_user.totp_secret)
        if not totp.verify(mfa_code):
            flash("Invalid MFA code.", "danger")
            _log_operator_event("operator_mfa_failed", "Invalid MFA code")
            return redirect(url_for("admin.operator_login"))

    # 3. Log success
    _log_operator_event("operator_login_success", "Operator authenticated")

    # 4. Redirect to next or admin dashboard
    next_url = request.form.get("next")
    return redirect(next_url or url_for("admin.dashboard"))


def _log_operator_event(event_type, message):
    """Write operator login events to FinancialAuditLog."""
    entry = FinancialAuditLog(
        actor_id=current_user.id,
        event_type=event_type,
        description=message,
        created_at=datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.commit()
