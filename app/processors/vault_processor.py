# =============================================================================
# FILE: app/processors/vault_processor.py
# DESCRIPTION: Vault processing logic. Uses canonical model imports from
#              app.models, ensures BankAccount ownership field matches model,
#              and guards DB flush/commit and Redis writes for deterministic
#              behavior.
# =============================================================================
import json
from datetime import datetime

from flask import current_app

from app import db
from app.models import BankAccount, BankTransaction
from app.models.vault_transaction import VaultTransaction
from app.utils.redis_utils import get_redis_client


def flag_anomaly(txn: VaultTransaction, acct: BankAccount) -> None:
    r = get_redis_client()
    if not r:
        current_app.logger.error(
            f"[flag_anomaly] Redis unavailable — cannot flag anomalies for acct_id={acct.id}"
        )
        return

    flags = []
    if txn.amount > 10000:
        flags.append("High-Value Deposit")
    if txn.method not in {"ach", "plaid", "manual"}:
        flags.append("Unknown Method")
    # If your intent is to check prior balance equality, fetch a prior snapshot.
    # Using current acct.balance may reflect post-update.
    if acct.balance == txn.amount:
        flags.append("Zero Balance Before Deposit")

    if flags:
        anomaly = {
            "txn_id": txn.id,
            "flags": flags,
            "amount": txn.amount,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            r.lpush(f"vault_anomalies:{acct.id}", json.dumps(anomaly))
        except Exception as e:
            current_app.logger.error(
                f"[flag_anomaly] Failed to push anomaly for acct_id={acct.id}: {e}"
            )


def record_daily_flow(user_id: int, amount: float, direction: str) -> None:
    r = get_redis_client()
    if not r:
        current_app.logger.error(
            f"[record_daily_flow] Redis unavailable — cannot record flow for user_id={user_id}"
        )
        return

    key = f"flow_snapshot:{user_id}:{datetime.utcnow().date()}"
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "amount": amount,
        "direction": direction,
    }
    try:
        r.rpush(key, json.dumps(payload))
    except Exception as e:
        current_app.logger.error(
            f"[record_daily_flow] Failed to push flow snapshot for user_id={user_id}: {e}"
        )


def process_vault_txn(txn: VaultTransaction) -> None:
    """
    Process a single reconciled vault transaction:
    - Update account balance
    - Create a BankTransaction record
    - Push Redis trace log
    - Flag anomalies
    - Record daily flow
    - Mark vault transaction as processed
    """
    # Ensure the ownership field matches BankAccount (user_id)
    acct = BankAccount.query.filter_by(user_id=txn.borrower_id, account_type="vault").first()
    if not acct:
        current_app.logger.warning(
            f"[process_vault_txn] Vault account not found for borrower_id={txn.borrower_id}"
        )
        return

    # Update balance and create bank transaction record
    prior_balance = acct.balance or 0.0
    acct.balance = prior_balance + txn.amount

    deposit = BankTransaction(
        to_account_id=acct.id,
        amount=txn.amount,
        txn_type="deposit",
        method=txn.method,
        timestamp=datetime.utcnow(),
    )
    db.session.add(deposit)

    # Ensure txn id is available for Redis tracing (works with integer PKs)
    try:
        db.session.flush()
    except Exception as e:
        current_app.logger.error(f"[process_vault_txn] DB flush failed: {e}")
        db.session.rollback()
        return

    # Redis trace log (best-effort)
    r = get_redis_client()
    if r:
        trace = {
            "timestamp": datetime.utcnow().isoformat(),
            "txn_id": txn.id,
            "bank_txn_id": getattr(deposit, "id", None),
            "amount": txn.amount,
            "method": txn.method,
            "to_account": acct.id,
            "borrower_id": txn.borrower_id,
        }
        try:
            r.lpush(f"vault_trace:{acct.id}", json.dumps(trace))
        except Exception as e:
            current_app.logger.error(
                f"[process_vault_txn] Failed to push vault trace for acct_id={acct.id}: {e}"
            )
    else:
        current_app.logger.error(
            f"[process_vault_txn] Redis unavailable — cannot push vault trace for acct_id={acct.id}"
        )

    # Anomaly flags and flow tracking
    flag_anomaly(txn, acct)
    record_daily_flow(txn.borrower_id, txn.amount, "inbound")

    # Mark vault transaction as processed (idempotent changes)
    txn.reconciled = False
    txn.processed_at = datetime.utcnow()

    # Commit changes with robust handling
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"[process_vault_txn] DB commit failed: {e}")
        db.session.rollback()
        raise


def process_reconciled_vaults() -> None:
    reconciled = VaultTransaction.query.filter_by(reconciled=True).all()
    if not reconciled:
        return

    for txn in reconciled:
        try:
            process_vault_txn(txn)
        except Exception as e:
            current_app.logger.error(
                f"[process_reconciled_vaults] Failed to process txn_id={txn.id}: {e}"
            )
            # continue processing next txn; individual failures do not block the batch
