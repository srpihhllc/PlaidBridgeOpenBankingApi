# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/agents/tracer.py

import json
from datetime import datetime

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

# Use the centralised Redis client
redis_client = get_redis_client()


def log_trace(agent, service, redis_key, ui_path):
    """
    Logs a trace event to the orchestration_tracer list in Redis.
    Falls back gracefully if Redis is unavailable.
    """
    event = {
        "agent": agent,
        "service": service,
        "redis": redis_key,
        "ui": ui_path,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if redis_client:
        try:
            redis_client.lpush("orchestration_tracer", json.dumps(event))
        except Exception as e:
            # Optional: log this somewhere cockpit‑visible
            print(f"⚠️ Failed to push trace event to Redis: {e}")
    else:
        # Optional: log this somewhere cockpit‑visible
        print("⚠️ Redis unavailable — trace event not recorded.")
