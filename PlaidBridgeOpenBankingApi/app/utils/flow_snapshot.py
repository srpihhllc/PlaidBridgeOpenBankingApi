# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/flow_snapshot.py

import json
from datetime import datetime

from flask import current_app

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client


def record_daily_flow(user_id, amount, direction):
    """
    Append a daily flow snapshot entry for a user.
    Falls back gracefully if Redis is unavailable.
    """
    r = get_redis_client()
    if not r:
        current_app.logger.error(
            f"[flow_snapshot] Redis unavailable — cannot record flow for user_id={user_id}"
        )
        return

    key = f"flow_snapshot:{user_id}:{datetime.utcnow().date()}"
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "amount": amount,
        "direction": direction,  # "inbound" or "outbound"
    }

    try:
        r.rpush(key, json.dumps(payload))
    except Exception as e:
        current_app.logger.error(
            f"[flow_snapshot] Failed to push flow snapshot for user_id={user_id}: {e}"
        )
