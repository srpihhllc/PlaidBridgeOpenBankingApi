# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/seed_mock_bank_transfers_audit.py

from datetime import datetime

import click
from flask import current_app

from app.extensions import db
from app.models import Transaction, User
from app.models.audit_log import AuditLog  # adjust import if your model lives elsewhere


@click.command("seed-mock-bank-transfers-audit")
def seed_mock_bank_transfers_audit():
    """
    Generate audit‑log entries for all mock bank transfers belonging to the subscriber.

    This command inspects existing Transaction rows and emits structured audit events
    into the cockpit audit log table. It is safe to run multiple times — events are
    deduplicated by (transaction_id, event_type).
    """

    logger = current_app.logger
    logger.info("🔍 Starting mock bank‑transfer audit seeding...")

    # -------------------------------------------------------------------------
    # 1. Resolve subscriber
    # -------------------------------------------------------------------------
    user = User.query.filter_by(email="subscriber@example.com").first()
    if not user:
        logger.error("❌ Subscriber not found. Seed subscriber first.")
        return

    # -------------------------------------------------------------------------
    # 2. Load all mock bank transfers for this user
    # -------------------------------------------------------------------------
    transfers = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.date.desc()).all()

    if not transfers:
        logger.warning("⚠️ No transactions found for subscriber — nothing to audit.")
        return

    logger.info(f"📦 Loaded {len(transfers)} transactions for audit processing.")

    # -------------------------------------------------------------------------
    # 3. Emit audit events
    # -------------------------------------------------------------------------
    created_count = 0

    for tx in transfers:
        event_type = "mock_bank_transfer_audit"

        # Deduplication: skip if event already exists
        existing = AuditLog.query.filter_by(transaction_id=tx.id, event_type=event_type).first()

        if existing:
            continue

        # Compute simple audit signals
        direction = "credit" if tx.amount > 0 else "debit"
        risk_flag = "high" if abs(tx.amount) > 5000 else "normal"

        audit_payload = {
            "transaction_id": tx.id,
            "amount": tx.amount,
            "direction": direction,
            "risk_flag": risk_flag,
            "category": tx.category,
            "timestamp": datetime.utcnow().isoformat(),
        }

        audit = AuditLog(
            user_id=user.id,
            transaction_id=tx.id,
            event_type=event_type,
            payload=audit_payload,
            created_at=datetime.utcnow(),
        )

        db.session.add(audit)
        created_count += 1

    db.session.commit()

    logger.info(f"✅ Created {created_count} new audit events.")
    logger.info("🎉 Mock bank‑transfer audit seeding complete.")
