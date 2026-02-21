# =============================================================================
# FILE: app/views/banking.py
# DESCRIPTION: Banking blueprint exposing account views.
# Provides user account listings, transaction history, and account info
# with safe error handling and template rendering.
# =============================================================================

from flask import Blueprint, abort, current_app, render_template

from app.models.bank_account import BankAccount
from app.models.transactions import Transaction
from app.models.user import User

# ✅ Use a clean, consistent blueprint name and prefix
banking_bp = Blueprint("banking", __name__, url_prefix="/accounts")


# ---------------------------------------------------------------------------
# List all accounts
# ---------------------------------------------------------------------------
@banking_bp.route("/", methods=["GET"])
def list_accounts():
    """Render a page showing all bank accounts in the system."""
    try:
        accounts = BankAccount.query.all()
        return render_template("accounts.html", accounts=accounts)
    except Exception as e:
        current_app.logger.error(f"❌ Error listing accounts: {e}")
        abort(500, description="Unable to load accounts at this time.")


# ---------------------------------------------------------------------------
# View accounts for a specific user
# ---------------------------------------------------------------------------
@banking_bp.route("/<int:user_id>", methods=["GET"])
def view_accounts(user_id: int):
    """Render the accounts page for a given user."""
    try:
        user = User.query.get_or_404(user_id)
        accounts = BankAccount.query.filter_by(user_id=user_id).all()
        return render_template("accounts.html", user=user, accounts=accounts)
    except Exception as e:
        current_app.logger.error(f"❌ Error rendering accounts for user {user_id}: {e}")
        abort(500, description="Unable to load accounts at this time.")


# ---------------------------------------------------------------------------
# Transaction history for a specific account
# ---------------------------------------------------------------------------
@banking_bp.route("/<int:account_id>/txns", methods=["GET"])
def account_txns(account_id: int):
    """Render transaction history for a specific account."""
    try:
        account = BankAccount.query.get_or_404(account_id)
        outgoing = account.outgoing_transactions.all()
        incoming = account.incoming_transactions.all()
        txns = outgoing + incoming
        velocity = len(txns)

        return render_template(
            "account_txns.html",
            account=account,
            txns=txns,
            velocity=velocity,
        )
    except Exception as e:
        current_app.logger.error(f"❌ Error rendering transactions for account {account_id}: {e}")
        abort(500, description="Unable to load transactions at this time.")


# ---------------------------------------------------------------------------
# Account info view (canonical, with real Transaction data)
# ---------------------------------------------------------------------------
@banking_bp.route("/<int:account_id>/info", methods=["GET"])
def account_info(account_id: int):
    """Render account info and statements for a specific account."""
    try:
        account = BankAccount.query.get_or_404(account_id)

        # Pull transactions for this account
        statements = (
            Transaction.query.filter_by(
                account_id=str(account_id)
            )  # account_id stored as string in Transaction
            .order_by(Transaction.date.desc())
            .all()
        )

        # Map into the structure expected by account_info.html
        statement_data = [
            {
                "date": txn.date.strftime("%Y-%m-%d"),
                "description": txn.name or txn.category or "Transaction",
                "amount": txn.amount,
            }
            for txn in statements
        ]

        return render_template(
            "account_info.html",
            account_balance=account.balance,
            statements=statement_data,
        )
    except Exception as e:
        current_app.logger.error(f"❌ Error rendering account info for account {account_id}: {e}")
        abort(500, description="Unable to load account info at this time.")
