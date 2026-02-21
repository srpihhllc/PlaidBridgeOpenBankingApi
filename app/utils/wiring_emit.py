# =============================================================================
# FILE: app/utils/wiring_emit.py
# DESCRIPTION: Unified emitter for template tracer + audit results.
#              Pushes consolidated wiring payloads into Redis for cockpit tiles.
# =============================================================================

import json
import logging

from app.utils.redis_utils import get_redis_client

_logger = logging.getLogger(__name__)


def wiring_emit(results: list[dict], ttl: int = 600) -> None:
    """
    Emit unified wiring results into Redis.
    - results: list of dicts with keys: endpoint, rule, template, status, error
    - ttl: time-to-live in seconds (default 600)
    """
    redis_client = get_redis_client()
    if not redis_client:
        _logger.error("Redis unavailable — cannot emit wiring results")
        return

    try:
        payload = json.dumps(results)
        redis_client.setex("audit:template_wiring", ttl, payload)
        _logger.info("✅ Emitted %d wiring results to Redis", len(results))
    except Exception as e:
        _logger.error("Failed to emit wiring results: %s", e)
