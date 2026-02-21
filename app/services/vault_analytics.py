# app/services/vault_analytics.py

from collections import defaultdict
from datetime import datetime, timedelta


def compute_vault_summary(vault_txns):
    total = sum(t.amount for t in vault_txns)
    deposits = sum(t.amount for t in vault_txns if t.amount > 0)
    withdrawals = sum(abs(t.amount) for t in vault_txns if t.amount < 0)

    return {
        "total_balance": total,
        "total_deposits": deposits,
        "total_withdrawals": withdrawals,
        "txn_count": len(vault_txns),
    }


def compute_vault_flow(vault_txns):
    """Return labels + values for the last 14 days."""
    today = datetime.utcnow().date()
    buckets = defaultdict(float)

    for t in vault_txns:
        d = t.created_at.date()
        if (today - d).days <= 14:
            buckets[d] += t.amount

    labels = []
    values = []

    for i in range(14, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%m-%d"))
        values.append(buckets.get(day, 0))

    return labels, values


def compute_vault_fraud_signals(vault_txns):
    """Simple fraud heuristics."""
    signals = []

    # Large transaction
    for t in vault_txns:
        if abs(t.amount) > 5000:
            signals.append(
                {
                    "type": "large_txn",
                    "amount": t.amount,
                    "created_at": t.created_at.isoformat(),
                }
            )

    # Rapid-fire transactions
    vault_txns_sorted = sorted(vault_txns, key=lambda x: x.created_at)
    for i in range(1, len(vault_txns_sorted)):
        delta = (
            vault_txns_sorted[i].created_at - vault_txns_sorted[i - 1].created_at
        ).total_seconds()
        if delta < 30:
            signals.append(
                {
                    "type": "rapid_fire",
                    "txn_id": vault_txns_sorted[i].id,
                    "seconds_between": delta,
                }
            )

    return signals
