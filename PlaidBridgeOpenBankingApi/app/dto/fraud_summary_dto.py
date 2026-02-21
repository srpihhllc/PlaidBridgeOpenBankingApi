# app/dto/fraud_summary_dto.py

from dataclasses import dataclass


@dataclass
class FraudSummaryDTO:
    total_risk_score: int
    flagged_transactions: list[dict]
    flagged_count: int
