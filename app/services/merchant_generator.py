# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/merchant_generator.py

import random
from datetime import datetime, timedelta

# Merchant registry with clustering, MCC codes, and spending patterns
MERCHANTS = [
    {
        "cluster": "coffee",
        "name": "Starbucks",
        "aliases": ["Starbucks #0421", "Starbucks Store 8812", "Starbucks"],
        "categories": ["Food and Drink", "Coffee Shop"],
        "mcc": "5814",
        "amount_range": (-4.50, -12.75),
        "spending_bias": {"morning": 0.65, "afternoon": 0.25, "evening": 0.10},
        "fraud_risk": 0.02,
        "location": {"city": "Seattle", "lat": 47.6097, "lon": -122.3331},
    },
    {
        "cluster": "groceries",
        "name": "Walmart",
        "aliases": ["Walmart Supercenter", "Walmart #1123", "Walmart"],
        "categories": ["Shops", "Supermarkets and Groceries"],
        "mcc": "5411",
        "amount_range": (-10, -180),
        "spending_bias": {"morning": 0.20, "afternoon": 0.50, "evening": 0.30},
        "fraud_risk": 0.04,
        "location": {"city": "Bentonville", "lat": 36.3729, "lon": -94.2088},
    },
    {
        "cluster": "gas",
        "name": "Shell Oil",
        "aliases": ["Shell Oil", "Shell Service Station", "Shell"],
        "categories": ["Travel", "Gas Stations"],
        "mcc": "5541",
        "amount_range": (-20, -90),
        "spending_bias": {"morning": 0.30, "afternoon": 0.40, "evening": 0.30},
        "fraud_risk": 0.06,
        "location": {"city": "Houston", "lat": 29.7604, "lon": -95.3698},
    },
    {
        "cluster": "subscription",
        "name": "Netflix",
        "aliases": ["Netflix.com", "Netflix Subscription"],
        "categories": ["Service", "Subscription"],
        "mcc": "4899",
        "amount_range": (-15, -15),
        "spending_bias": {"morning": 0.05, "afternoon": 0.10, "evening": 0.85},
        "fraud_risk": 0.01,
        "location": {"city": "Los Gatos", "lat": 37.2358, "lon": -121.9624},
    },
    {
        "cluster": "rideshare",
        "name": "Uber",
        "aliases": ["Uber Trip", "Uber *EATS", "Uber"],
        "categories": ["Travel", "Ride Share"],
        "mcc": "4121",
        "amount_range": (-8, -45),
        "spending_bias": {"morning": 0.15, "afternoon": 0.35, "evening": 0.50},
        "fraud_risk": 0.08,
        "location": {"city": "San Francisco", "lat": 37.7749, "lon": -122.4194},
    },
]


def weighted_time_of_day():
    hour = random.randint(0, 23)
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    return "evening"


def generate_plaid_style_transaction():
    merchant = random.choice(MERCHANTS)

    # Pick alias for clustering realism
    name = random.choice(merchant["aliases"])

    # Spending pattern realism
    tod = weighted_time_of_day()
    bias = merchant["spending_bias"][tod]

    # Amount
    low, high = merchant["amount_range"]
    amount = round(random.uniform(low, high) * (1 + (bias * 0.1)), 2)

    # Fraud likelihood scoring
    fraud_score = round(merchant["fraud_risk"] * random.uniform(0.8, 1.4), 3)

    # Payment metadata (Plaid-style)
    payment_meta = {
        "reference_number": f"RF{random.randint(100000,999999)}",
        "ppd_id": f"PPD{random.randint(1000,9999)}",
        "payment_method": random.choice(["card_present", "card_not_present", "online"]),
    }

    # Location object
    location = merchant["location"]

    return {
        "name": name,
        "category": merchant["categories"][-1],
        "category_hierarchy": merchant["categories"],
        "mcc": merchant["mcc"],
        "cluster": merchant["cluster"],
        "description": name,
        "amount": amount,
        "date": datetime.utcnow() - timedelta(days=random.randint(1, 60)),
        "is_pending": False,
        "fraud_score": fraud_score,
        "location": location,
        "payment_meta": payment_meta,
    }
