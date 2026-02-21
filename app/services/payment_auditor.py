# app/services/payment_auditor.py

import json
import random
from datetime import datetime

from flask import current_app

from app.utils.redis_utils import get_redis_client


def audit_processor_logs(processor_name, transactions):
    """
    Simulates a payment processor audit, analyzing transactions for anomalies.
    """

    # Initialize the audit results structure
    audit_results = {
        "processor_name": processor_name,
        "audit_date": datetime.utcnow().isoformat(),
        "stats": {
            "total_transactions": len(transactions),
            "flagged_anomalies": 0,
            "total_value_audited": 0.0,
            "risk_score": 0.0,
        },
        "flagged_transactions": [],
    }

    # Heuristic-based anomaly detection
    high_value_threshold = 5000.0
    anomalous_keywords = ["suspicious", "fraud", "unusual transfer"]

    total_value = 0.0
    for tx in transactions:
        tx_id = tx.get("id", f"tx_{random.randint(1000, 9999)}")
        amount = float(tx.get("amount", 0))
        description = tx.get("description", "").lower()

        # Add to total value
        total_value += abs(amount)

        # Start with a base score for each transaction
        tx_risk_score = 0.0
        flag_reasons = []

        # Check for high-value transactions
        if abs(amount) > high_value_threshold:
            tx_risk_score += 0.5
            flag_reasons.append("High-value transaction")

        # Check for keywords in description
        if any(keyword in description for keyword in anomalous_keywords):
            tx_risk_score += 0.4
            flag_reasons.append("Description contains anomalous keyword")

        # Simulate a random "unknown" factor
        tx_risk_score += random.uniform(0.0, 0.1)

        # If any flags were triggered, add to the flagged list
        if flag_reasons:
            audit_results["stats"]["flagged_anomalies"] += 1
            audit_results["flagged_transactions"].append(
                {
                    "id": tx_id,
                    "amount": amount,
                    "date": tx.get("date"),
                    "description": description,
                    "reasons": flag_reasons,
                    "risk_score": round(min(tx_risk_score, 1.0), 3),
                }
            )

    # Calculate overall risk score (average of flagged transactions)
    if audit_results["stats"]["flagged_anomalies"] > 0:
        total_flagged_score = sum(t["risk_score"] for t in audit_results["flagged_transactions"])
        audit_results["stats"]["risk_score"] = round(
            total_flagged_score / audit_results["stats"]["flagged_anomalies"], 3
        )

    audit_results["stats"]["total_value_audited"] = round(total_value, 2)

    # Log the audit event to Redis for a dashboard or monitoring
    log_key = f"audit_log:{processor_name}:{datetime.utcnow().timestamp()}"
    client = getattr(current_app, "redis_client", None) or get_redis_client()

    if client:
        try:
            client.setex(log_key, 86400 * 7, json.dumps(audit_results))
        except Exception as e:
            current_app.logger.error(f"[payment_auditor] Redis setex failed for {log_key} — {e}")
    else:
        current_app.logger.error(
            f"[payment_auditor] Redis unavailable — skipping setex for {log_key}"
        )

    return audit_results


# Example Usage (for testing the function)
if __name__ == "__main__":
    mock_transactions = [
        {
            "id": "tx_001",
            "amount": 25.50,
            "date": "2025-08-20",
            "description": "Coffee Shop",
        },
        {
            "id": "tx_002",
            "amount": 6000.00,
            "date": "2025-08-20",
            "description": "Vendor Payment",
        },  # High value
        {
            "id": "tx_003",
            "amount": 120.00,
            "date": "2025-08-19",
            "description": "Retail Store",
        },
        {
            "id": "tx_004",
            "amount": -7500.00,
            "date": "2025-08-19",
            "description": "unusual transfer",
        },  # High value & keyword
        {
            "id": "tx_005",
            "amount": 50.00,
            "date": "2025-08-18",
            "description": "Groceries",
        },
    ]
    audit_data = audit_processor_logs("Stripe", mock_transactions)
    print(json.dumps(audit_data, indent=2))
