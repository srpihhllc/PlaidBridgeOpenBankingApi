# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/telemetry/emitters/access_token.py

import json

from app.utils.redis_utils import get_redis_client


def emit_access_token_trace(token_obj):
    """
    Emits a TTL-backed trace for access token lifecycle.
    Uses cockpit-grade Redis client with health pulse support.
    """
    client = get_redis_client()
    if not client:
        return  # Redis unavailable — skip emission

    key = f"ttl:access_token:{token_obj.user_id}:{token_obj.id}"
    payload = {
        "token": token_obj.token,
        "issued_at": token_obj.created_at.isoformat(),
        "expires_at": (token_obj.expires_at.isoformat() if token_obj.expires_at else None),
    }

    try:
        client.setex(key, 3600, json.dumps(payload))  # 1-hour TTL
    except Exception:
        # Optional: log or emit fallback TTL trace
        pass
