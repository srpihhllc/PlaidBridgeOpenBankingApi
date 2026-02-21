# app/tiles/emit_view_failure_probe.py

from flask import current_app

from app.tiles.view_failure_probe import collect_view_failures
from app.utils.redis_utils import get_redis_client


def emit_view_failure_probe():
    """
    Emit the View Failure Probe payload to Redis with a 5-minute TTL.
    Guards against Redis unavailability so the cockpit tile stays green.
    """
    key = "ttl:cockpit:view_failures"
    payload = collect_view_failures()

    client = getattr(current_app, "redis_client", None) or get_redis_client()
    if client:
        try:
            client.setex(key, 300, str(payload))  # TTL = 5 minutes
            current_app.logger.info(
                "[tiles.emit_view_failure_probe.emit_view_failure_probe] TTL emitted " f"for {key}"
            )
        except Exception as e:
            current_app.logger.error(
                "[tiles.emit_view_failure_probe.emit_view_failure_probe] Redis setex "
                f"failed for {key} — {e}"
            )
    else:
        current_app.logger.error(
            "[tiles.emit_view_failure_probe.emit_view_failure_probe] Redis unavailable "
            f"— skipping setex for {key}"
        )
