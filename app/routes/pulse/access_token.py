# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/pulse/access_token.py

"""
/home/srpihhllc/PlaidBridgeOpenBankingApi/app/routes/pulse/access_token.py

Pulse endpoint for access tokens.

- Supports:
  GET /pulse/access_token?user_id=<id>
  GET /pulse/access_token/<user_id>

- Works with numeric IDs and UUID-like string IDs.
- Returns an empty list if Redis is unavailable or no traces found.
"""

import json
from collections.abc import Iterable

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.utils.redis_utils import get_redis_client

bp = Blueprint("pulse_access_token", __name__)


def _collect_traces_for_user(user_id) -> list:
    """
    Read Redis keys matching ttl:access_token:{user_id}:* and return parsed JSON list.
    user_id may be int or str (UUID); function is resilient to bytes/decoding issues.
    """
    client = get_redis_client()
    if not client:
        return []

    pattern = f"ttl:access_token:{user_id}:*"

    traces = []
    try:
        keys_iter: Iterable = client.scan_iter(match=pattern)
    except Exception:
        # If scan_iter fails for whatever reason, return empty gracefully
        return []

    for key in keys_iter:
        try:
            raw = client.get(key)
            if not raw:
                continue
            # redis-py may return bytes or str depending on decode_responses
            if isinstance(raw, bytes | bytearray):
                raw = raw.decode("utf-8", errors="ignore")
            # Expect JSON stored in the value
            parsed = json.loads(raw)
            traces.append(parsed)
        except Exception:
            # Skip any malformed entry
            continue

    return traces


@bp.route("/pulse/access_token", methods=["GET"])
def pulse_access_token_query():
    """
    Canonical endpoint used by client code:
      GET /pulse/access_token?user_id=<id>

    If user_id is omitted, attempt to use current_user.id when authenticated.
    Returns JSON array of traces (possibly empty).
    """
    user_id = request.args.get("user_id")
    if not user_id:
        # fall back to current user if available
        try:
            if current_user and getattr(current_user, "is_authenticated", False):
                user_id = current_user.get_id()
        except Exception:
            user_id = None

    if not user_id:
        # Nothing to query for — return empty list
        return jsonify([])

    traces = _collect_traces_for_user(user_id)
    return jsonify(traces)


# Backward-compatible permissive route that accepts numeric IDs or UUID-like strings.
# This avoids a 404 when a cached client calls /pulse/access_token/<uuid>
@bp.route("/pulse/access_token/<user_id>", methods=["GET"])
def pulse_access_token(user_id):
    """
    Backwards-compatible route. Accepts user_id as path segment (string).
    Delegates to the same collector.
    """
    traces = _collect_traces_for_user(user_id)
    return jsonify(traces)
