import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import or_
from app.models import BankAccount, BankStatement, BankTransaction
from app.services.bank_statement_generator import render_branded_bank_statement_pdf

logger = logging.getLogger(__name__)

def get_last_statement_data(user_id: int | str) -> dict[str, Any] | None:
    try:
        stmt = BankStatement.query.filter_by(user_id=user_id).order_by(BankStatement.timestamp.desc(), BankStatement.id.desc()).first()
        if not stmt:
            logger.warning(f"[get_last_statement_data] No statements found for user_id={user_id}")
            return None
        ts = stmt.timestamp or stmt.created_at
        return {"id": stmt.id, "user_id": stmt.user_id, "bank": stmt.bank, "account": stmt.account, "name": stmt.name, "txn_count": stmt.txn_count, "source_api": stmt.source_api, "generated_at": ts.isoformat() if ts else None}
    except Exception as e:
        logger.error(f"[get_last_statement_data] Failed for user_id={user_id}: {e}", exc_info=True)
        return None

def generate_statement_pdf(user_id: int | str, lender_id: int | str | None = None) -> bytes:
    try:
        accounts = BankAccount.query.filter_by(user_id=user_id).all()
        account_ids = [acct.id for acct in accounts]
        primary_acct = accounts[0] if accounts else None
        last_stmt = get_last_statement_data(user_id)
        bank_name = (last_stmt.get("bank") if last_stmt else None) or "PlaidBridge BaaS Treasury"
        account_number = primary_acct.account_number if (primary_acct and primary_acct.account_number) else (last_stmt.get("account") if last_stmt else f"SUB-{str(user_id)[:8]}")
        tx_rows: list[dict[str, Any]] = []
        if account_ids:
            txns = BankTransaction.query.filter(or_(BankTransaction.from_account_id.in_(account_ids), BankTransaction.to_account_id.in_(account_ids))).order_by(BankTransaction.timestamp.desc()).limit(100).all()
            for tx in txns:
                is_credit = tx.to_account_id in account_ids and tx.from_account_id not in account_ids
                signed_amt = float(tx.amount or 0.0) * (1.0 if is_credit else -1.0)
                desc = f"{(tx.payment_channel or tx.txn_type or 'TRANSFER').upper()} ({tx.method or 'electronic'})"
                tx_rows.append({"date": tx.timestamp.strftime("%Y-%m-%d") if tx.timestamp else datetime.now(timezone.utc).strftime("%Y-%m-%d"), "description": desc, "amount": signed_amt})
        if not tx_rows:
            tx_rows.append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "description": "Opening Balance / Verified BaaS Account", "amount": float(primary_acct.balance) if (primary_acct and primary_acct.balance is not None) else 0.0})
        return render_branded_bank_statement_pdf(bank_name=bank_name, account_number=account_number, transactions=tx_rows, lender_id=lender_id)
    except Exception as e:
        logger.error(f"[generate_statement_pdf] Failed for user_id={user_id}: {e}", exc_info=True)
        return b""
