# app/utils/loan_utils.py


def analyze_loan_agreement(text):
    """
    Analyzes loan agreement text for key terms like interest rates, repayment dates, penalties.
    Returns a dict with extracted insights.
    """
    keywords = [
        "interest rate",
        "repayment",
        "term",
        "default",
        "penalty",
        "grace period",
    ]
    findings = {kw: kw in text.lower() for kw in keywords}
    return {
        "total_words": len(text.split()),
        "matched_keywords": [kw for kw, present in findings.items() if present],
        "keyword_presence": findings,
    }
