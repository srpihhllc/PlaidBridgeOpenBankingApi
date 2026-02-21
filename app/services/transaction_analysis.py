# =============================================================================
# FILE: app/services/transaction_analysis.py
# DESCRIPTION:
#   Summaries, category grouping, and simple fraud scoring.
# =============================================================================

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from .transaction_dto import TransactionDTO


@dataclass
class TransactionSummary:
    total_amount: float
    income: float
    expenses: float
    net_cash_flow: float


@dataclass
class CategoryBreakdown:
    by_category: dict[str, float]


@dataclass
class FraudInsight:
    flagged: list[TransactionDTO]
    risk_score: float  # 0–100


def build_summary(txns: Iterable[TransactionDTO]) -> TransactionSummary:
    total = 0.0
    income = 0.0
    expenses = 0.0

    for t in txns:
        total += t.amount
        if t.amount > 0:
            income += t.amount
        elif t.amount < 0:
            expenses += abs(t.amount)

    return TransactionSummary(
        total_amount=total,
        income=income,
        expenses=expenses,
        net_cash_flow=income - expenses,
    )


def build_category_breakdown(txns: Iterable[TransactionDTO]) -> CategoryBreakdown:
    bucket = defaultdict(float)
    for t in txns:
        bucket[t.category] += t.amount
    return CategoryBreakdown(by_category=dict(bucket))


def compute_fraud_insights(txns: Iterable[TransactionDTO]) -> FraudInsight:
    flagged = []
    risk = 0.0

    for t in txns:
        # Very simple heuristic (replace with real model later):
        if abs(t.amount) > 5000:
            flagged.append(t)
            risk += 10.0
        if t.category.lower() in {"fraud", "chargeback"}:
            flagged.append(t)
            risk += 20.0

    risk_score = max(0.0, min(100.0, risk))
    # Deduplicate flagged list
    seen = set()
    unique_flagged = []
    for t in flagged:
        if t.id not in seen:
            seen.add(t.id)
            unique_flagged.append(t)

    return FraudInsight(flagged=unique_flagged, risk_score=risk_score)
