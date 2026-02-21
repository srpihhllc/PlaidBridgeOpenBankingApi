# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/cockpit/transfers.py

from app.services.bank_transaction_fraud import score_bank_transaction_fraud
from flask import render_template
from flask_login import login_required

from app.models import BankTransaction

from . import cockpit_ui


@cockpit_ui.route("/dashboard/transfers")
@login_required
def transfers_dashboard():
    # Pull recent transfers
    recent = BankTransaction.query.order_by(BankTransaction.timestamp.desc()).limit(200).all()

    suspicious = []
    for txn in recent:
        risk = score_bank_transaction_fraud(txn)
        if risk >= 0.6:
            suspicious.append((txn, risk))

    # Sort suspicious by risk descending
    suspicious.sort(key=lambda pair: pair[1], reverse=True)
    suspicious = suspicious[:25]

    return render_template(
        "cockpit/dashboard_transfers.html",
        suspicious_transfers=suspicious,
    )
