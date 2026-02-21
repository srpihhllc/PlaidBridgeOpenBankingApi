# app/routes/cockpit_routes.py

from flask import Blueprint, jsonify, render_template
from flask_login import login_required

from app.models import CreditLedger, PaymentLog, User

cockpit_bp = Blueprint("cockpit_routes_bp", __name__, url_prefix="/admin/cockpit")


@cockpit_bp.route("/cockpit/exposure/<int:user_id>")
def cockpit_exposure_tile(user_id):
    """Returns repayment vs credit limit summary for dashboard meter."""
    ledger_entries = CreditLedger.query.filter_by(user_id=user_id).all()
    payment_entries = PaymentLog.query.filter_by(user_id=user_id).all()

    total_limit = sum(entry.credit_limit for entry in ledger_entries)
    total_repaid = sum(entry.amount for entry in payment_entries)
    ratio = total_repaid / total_limit if total_limit else 0

    status = "normal"
    if ratio < 0.8:
        status = "warning"
    elif ratio < 0.5:
        status = "risk"

    return jsonify(
        {
            "user_id": user_id,
            "credit_limit": total_limit,
            "repaid": total_repaid,
            "exposure_ratio": round(ratio, 2),
            "status": status,
        }
    )


@cockpit_bp.route("/borrower-card-grid")
@login_required
def borrower_card_grid():
    borrowers = User.query.filter_by(role="borrower").all()
    cards = []
    for b in borrowers:
        score = b.credit_score
        color = "green" if score > 700 else "orange" if score > 600 else "red"
        cards.append(
            {
                "name": b.username,
                "score": score,
                "color": color,
                "card_number": b.card_number,
                "expiration": b.card_expiration,
                "cvv": b.card_cvv,
            }
        )
    return render_template("admin/cockpit/borrower_card_grid.html", cards=cards)
