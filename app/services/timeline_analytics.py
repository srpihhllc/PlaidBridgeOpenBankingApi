# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/timeline_analytics.py

from collections import defaultdict

from app.dto.transaction_dto import TransactionDTO


def compute_timeline(transactions: list[TransactionDTO]):
    """
    Returns a list of {date, net_flow} sorted by date ascending.
    """
    buckets: dict[str, float] = defaultdict(float)

    for tx in transactions:
        date_key = tx.date[:10]  # YYYY-MM-DD
        buckets[date_key] += float(tx.amount)

    timeline = [{"date": d, "net_flow": amt} for d, amt in buckets.items()]
    timeline.sort(key=lambda x: x["date"])
    return timeline
