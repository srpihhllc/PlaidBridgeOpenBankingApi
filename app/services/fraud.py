# app/services/fraud.py

import json
import random
from datetime import datetime

from flask import current_app

from app.utils.redis_utils import get_redis_client


def analyze_transaction(tx):
    """
    Analyze a transaction for potential fraud signals.
    """
    score = 0.0
    flags = []

    # Heuristics
    amount = float(tx.get("amount", 0))
    description = tx.get("description", "").lower()

    if abs(amount) > 5000:
        score += 0.4
        flags.append("High-value transaction")

    if "gift cards" in description:
        score += 0.3
        flags.append("Possible laundering keyword")

    if not description.strip():
        score += 0.2
        flags.append("Missing description")

    # Add randomness (placeholder for ML model inference later)
    score += random.uniform(0.0, 0.1)

    result = {
        "fraud_score": round(min(score, 1.0), 3),
        "flags": flags,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # 🔐 Log to Redis for dashboarding
    key = f"fraud_log:{tx.get('id', 'tx')}-{datetime.utcnow().timestamp()}"
    client = getattr(current_app, "redis_client", None) or get_redis_client()
    if client:
        try:
            client.setex(key, 86400, json.dumps(result))  # expire in 24 hours
        except Exception as e:
            current_app.logger.error(
                f"[fraud.analyze_transaction] Redis setex failed for {key} — {e}"
            )
    else:
        current_app.logger.error(
            f"[fraud.analyze_transaction] Redis unavailable — skipping setex for {key}"
        )

    return result


def analyze_transactions_batch(transactions):
    from collections import Counter

    results = []
    scores = []

    for tx in transactions:
        tx_id = tx.get("id", f"tx_{random.randint(1000, 9999)}")
        result = analyze_transaction(tx)
        result["id"] = tx_id
        result["amount"] = tx.get("amount")
        result["description"] = tx.get("description", "")
        results.append(result)
        scores.append(result["fraud_score"])

    # 🔢 Stats
    total = len(results)
    flagged = sum(1 for r in results if r["fraud_score"] >= 0.5)
    average_score = round(sum(scores) / total, 3) if total else 0

    # 📊 Risk buckets
    buckets = Counter()
    for score in scores:
        if score >= 0.8:
            buckets["high"] += 1
        elif score >= 0.5:
            buckets["medium"] += 1
        else:
            buckets["low"] += 1

    # 🏆 Top 5
    top_risky = sorted(results, key=lambda r: r["fraud_score"], reverse=True)[:5]

    return {
        "results": results,
        "stats": {
            "total": total,
            "flagged": flagged,
            "average_score": average_score,
            "risk_buckets": dict(buckets),
            "top_5_riskiest": top_risky,
        },
    }


def detect_fraudulent_transaction(tx):
    return analyze_transaction(tx)


def analyze_loan_agreement(agreement_data):
    """
    Simulate analysis of a loan agreement for compliance signals.
    """
    violations = agreement_data.get("violation_count", 0)
    score = 100 - (violations * 15)

    return {
        "agreement_id": agreement_data.get("id", "unknown"),
        "violations": violations,
        "ai_flagged": violations > 0,
        "compliance_score": max(score, 0),
    }


def execute_smart_contract(loan_agreement_id):
    """
    Simulates smart contract execution and emits Redis trace packet.
    """
    result = {
        "agreement_id": loan_agreement_id,
        "status": "executed",
        "violations": random.randint(0, 3),
        "timestamp": datetime.utcnow().isoformat(),
    }

    if result["violations"] >= 3:
        result["status"] = "flagged"
        result["detail"] = "Agreement auto-locked due to violation threshold"
    elif result["violations"] > 0:
        result["status"] = "warned"
        result["detail"] = "Contract passed with warning"

    key = f"contract_log:{loan_agreement_id}:{datetime.utcnow().timestamp()}"
    client = getattr(current_app, "redis_client", None) or get_redis_client()
    if client:
        try:
            client.setex(key, 86400, json.dumps(result))
        except Exception as e:
            current_app.logger.error(
                f"[fraud.execute_smart_contract] Redis setex failed for {key} — {e}"
            )
    else:
        current_app.logger.error(
            f"[fraud.execute_smart_contract] Redis unavailable — skipping setex for {key}"
        )

    return result
