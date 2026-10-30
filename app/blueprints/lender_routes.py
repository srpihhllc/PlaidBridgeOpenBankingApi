# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/lender_routes.py

from typing import Any

from flask import Blueprint, abort, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FinancialSnapshot, LoanApplication

lender_bp = Blueprint("lender", __name__, url_prefix="/lender")


def get_authorized_application(application_id: int) -> Any:
    """Return an application the current lender is permitted to review."""
    if getattr(current_user, "role", None) != "lender":
        abort(403)

    application = db.session.get(LoanApplication, application_id)
    if application is None:
        abort(404)

    # Require an active, subscriber-approved application belonging to this lender.
    if (
        application.lender_id != str(current_user.id)
        or application.status != "active"
        or application.subscriber_consent_at is None
        or application.access_revoked_at is not None
    ):
        # Avoid revealing whether another lender's application exists.
        abort(404)

    return application


@lender_bp.route(
    "/applications/<int:application_id>/snapshots",
    methods=["GET"],
)
@login_required
def application_snapshots(application_id: int):
    """Return snapshots for an application the current lender may review."""
    application = get_authorized_application(application_id)

    snapshots = (
        FinancialSnapshot.query
        .filter_by(application_id=application.id)
        .order_by(FinancialSnapshot.created_at.desc())
        .all()
    )

    # Return only fields needed for loan review.
    return (
        jsonify(
            {
                "application_id": application.id,
                "subscriber_id": application.subscriber_id,
                "snapshots": [
                    {
                        "captured_at": snapshot.created_at.isoformat(),
                        "data": snapshot.loan_review_data,
                    }
                    for snapshot in snapshots
                ],
            }
        ),
        200,
    )