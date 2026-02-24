# =============================================================================
# FILE: app/tiles/ttl_dashboard_tile.py
# DESCRIPTION: Cockpit tile emitter for TTL telemetry + MFA metrics.
#              Publishes summary metrics into Redis for operator dashboards.
# =============================================================================

import logging
from datetime import datetime

from app.utils.redis import redis_scan_json, redis_set_json

from app.cockpit.telemetry.emitters.ttl import ttl_summary

TTL_DASHBOARD_KEY = "cockpit:ttl_dashboard"
TTL_DASHBOARD_TTL_SECONDS = 60  # prevent stale tiles

_logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# MFA Metrics Collector
# -----------------------------------------------------------------------------
def collect_mfa_metrics() -> dict:
    """
    Collect MFA success/failure/lockout metrics from Redis.
    Keys expected:
      - mfa:{user_id}:{code} → ephemeral codes
      - mfa:fail:{user_id}   → fail counters
    """
    metrics = {"success": 0, "failures": 0, "locked_out": 0}

    try:
        # Scan Redis for MFA fail counters
        fail_keys = redis_scan_json("mfa:fail:*")
        for _key, value in fail_keys.items():
            fails = int(value or 0)
            metrics["failures"] += fails
            if fails >= 3:  # lockout threshold
                metrics["locked_out"] += 1

        # Scan Redis for active MFA codes
        active_codes = redis_scan_json("mfa:*:*")
        metrics["success"] = len(active_codes)

    except Exception as e:
        _logger.error("❌ Failed to collect MFA metrics: %s", e, exc_info=True)

    return metrics


# -----------------------------------------------------------------------------
# Tile Builder
# -----------------------------------------------------------------------------
def build_tile() -> dict:
    """
    Build the cockpit tile payload with TTL + MFA metrics.
    Includes:
      - version
      - timestamp
      - ttl telemetry
      - mfa metrics
    """
    try:
        ttl_data = ttl_summary()
    except Exception as e:
        _logger.error("❌ TTL summary failed: %s", e, exc_info=True)
        ttl_data = {"error": "ttl_summary_failed"}

    tile = {
        "version": 1,
        "timestamp": datetime.utcnow().isoformat(),
        "ttl": ttl_data,
        "mfa": collect_mfa_metrics(),
    }

    return tile


# -----------------------------------------------------------------------------
# Redis Emitter
# -----------------------------------------------------------------------------
def emit_to_redis() -> None:
    """
    Emits TTL + MFA summary to Redis for cockpit overlay.
    """
    try:
        tile = build_tile()
        redis_set_json(TTL_DASHBOARD_KEY, tile, ttl=TTL_DASHBOARD_TTL_SECONDS)
        _logger.info("[📡] TTL dashboard emitted → %s", TTL_DASHBOARD_KEY)
    except Exception as e:
        _logger.error("❌ Failed to emit TTL dashboard telemetry: %s", e, exc_info=True)


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------
def run() -> None:
    """
    CLI-compatible entry point for TTL dashboard emission.
    """
    print("[🔧] Emitting TTL dashboard telemetry...")
    emit_to_redis()
    print("[✅] TTL dashboard emission complete.")
