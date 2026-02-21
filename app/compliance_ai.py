# app/compliance_ai.py

import logging
from datetime import datetime, timedelta

from app.models import FraudReport, Transaction  # ✅ Keep this!


def predict_fraud_trends():
    """
    AI-powered fraud trend analysis based on recent transaction data.

    Returns:
      dict: Fraud trend insights including high-risk categories.
    """
    try:
        # Analyze recent fraud cases within the last 30 days
        fraud_cases = FraudReport.query.filter(
            FraudReport.timestamp >= datetime.utcnow() - timedelta(days=30)
        ).all()

        if not fraud_cases:
            return {
                "status": "low risk",
                "trend": "No significant fraud patterns detected",
            }

        # Extract transaction details from fraud cases
        risk_categories = {}
        for case in fraud_cases:
            txn = Transaction.query.get(case.transaction_id)
            category = txn.description.split()[0] if txn else "Unknown"

            risk_categories[category] = risk_categories.get(category, 0) + 1

        # Determine risk level based on transaction patterns
        max_category = max(risk_categories, key=risk_categories.get)
        risk_level = "high risk" if risk_categories[max_category] > 5 else "moderate risk"

        fraud_summary = {
            "status": risk_level,
            "high_risk_category": max_category,
            "cases_analyzed": len(fraud_cases),
            "trend": f"Fraud patterns detected in {max_category} transactions.",
        }

        logging.info(f"Generated Fraud Trend Analysis: {fraud_summary}")
        return fraud_summary

    except Exception as e:
        logging.error(f"🚨 Error in fraud trend prediction: {e}")
        return {"status": "error", "message": str(e)}
