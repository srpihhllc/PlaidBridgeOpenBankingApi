# app/services/fraud_analytics.py


from app.dto.fraud_summary_dto import FraudSummaryDTO
from app.dto.transaction_dto import TransactionDTO

SUSPICIOUS_KEYWORDS = ["crypto", "gambling", "casino", "bet", "wire", "overseas"]


def compute_fraud_summary(transactions: list[TransactionDTO]) -> FraudSummaryDTO:
    flagged = []
    risk_score = 0

    for txn in transactions:
        amt = float(txn.amount)
        desc = (txn.description or "").lower()

        score = 0

        # Rule 1: Large withdrawals
        if amt < -500:
            score += 30

        # Rule 2: Suspicious keywords
        if any(k in desc for k in SUSPICIOUS_KEYWORDS):
            score += 40

        # Rule 3: High‑velocity small transactions
        if -20 < amt < 0:
            score += 10

        if score > 0:
            flagged.append(
                {
                    "id": txn.id,
                    "amount": amt,
                    "description": txn.description,
                    "score": score,
                }
            )
            risk_score += score

    return FraudSummaryDTO(
        total_risk_score=risk_score,
        flagged_transactions=flagged,
        flagged_count=len(flagged),
    )
