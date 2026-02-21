# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/funds.py

from datetime import datetime

from flask import Blueprint, current_app, redirect, render_template, request

from app import db
from app.models import BankAccount, BankTransaction
from app.utils.redis_utils import get_redis_client  # centralised, SSL‑safe client

funds_bp = Blueprint("funds_bp", __name__, url_prefix="/transfer")


@funds_bp.route("/", methods=["GET", "POST"])
def transfer_funds():
    accounts = BankAccount.query.all()

    if request.method == "POST":
        try:
            from_id = int(request.form.get("from_id", "0"))
            to_id = int(request.form.get("to_id", "0"))
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            current_app.logger.warning("[funds.transfer_funds] invalid form values")
            return render_template("transfer.html", accounts=accounts, error="Invalid input")

        from_acct = BankAccount.query.get(from_id)
        to_acct = BankAccount.query.get(to_id)

        if not from_acct or not to_acct:
            current_app.logger.warning("[funds.transfer_funds] account not found")
            return render_template("transfer.html", accounts=accounts, error="Account not found")

        if amount <= 0:
            current_app.logger.warning("[funds.transfer_funds] non-positive transfer amount")
            return render_template(
                "transfer.html", accounts=accounts, error="Amount must be positive"
            )

        if from_acct.balance >= amount:
            from_acct.balance -= amount
            to_acct.balance += amount

            txn = BankTransaction(
                from_account_id=from_id,
                to_account_id=to_id,
                amount=amount,
                txn_type="transfer",
                method="manual",
                timestamp=datetime.utcnow(),
            )
            db.session.add(txn)

            # Redis trace — safe, centralised
            r = get_redis_client()
            if r:
                try:
                    # store a short trace keyed by the transaction id (set after flush/commit)
                    db.session.flush()  # ensure txn.id is available when using integer PKs
                    try:
                        r.set(
                            f"capital_move:{txn.id}",
                            f"Transferred ${amount} from {from_id} → {to_id}",
                        )
                    except Exception as e:
                        current_app.logger.warning(
                            f"[funds.transfer_funds] Redis write failed: {e}"
                        )
                except Exception as e:
                    current_app.logger.warning(f"[funds.transfer_funds] DB flush failed: {e}")

            db.session.commit()
            # Redirect to account page by user_id (BankAccount.user_id is the canonical owner)
            return redirect(f"/accounts/{from_acct.user_id}")

        return render_template("transfer.html", accounts=accounts, error="Insufficient funds")

    return render_template("transfer.html", accounts=accounts)
