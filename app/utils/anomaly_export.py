# =============================================================================
# FILE: app/utils/anomaly_export.py
# DESCRIPTION: Cockpit-grade anomaly export from Redis to CSV with safe fallbacks.
# =============================================================================

import csv
import json
import logging
from datetime import datetime
from typing import Any

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

_logger = logging.getLogger(__name__)


def export_anomalies_to_csv(filepath: str = "anomaly_trace_export.csv") -> None:
    """
    Export all vault anomalies from Redis to a CSV file.
    - Each anomaly is expected to be a JSON object in a Redis list.
    - Falls back gracefully if Redis is unavailable or data is malformed.
    - Logs detailed operator-visible telemetry for cockpit dashboards.
    """
    r = get_redis_client()
    if not r:
        _logger.error("[anomaly_export] Redis unavailable — cannot export anomalies")
        return

    try:
        keys: list[bytes] = r.keys("vault_anomalies:*")
    except Exception as exc:
        _logger.exception("[anomaly_export] Failed to fetch anomaly keys: %s", exc)
        return

    if not keys:
        _logger.info("[anomaly_export] No anomaly keys found in Redis")
        return

    try:
        with open(filepath, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Account ID", "Txn ID", "Amount", "Flags", "Timestamp"])

            for key in keys:
                try:
                    acct_id = key.decode().split(":", 1)[1]
                except Exception:
                    acct_id = "UNKNOWN"

                try:
                    entries = r.lrange(key, 0, -1)
                except Exception as exc:
                    _logger.error("[anomaly_export] Failed to read list for key=%s: %s", key, exc)
                    continue

                for entry in entries:
                    try:
                        obj: dict[str, Any] = json.loads(entry)
                    except (TypeError, json.JSONDecodeError) as exc:
                        _logger.warning(
                            "[anomaly_export] Skipping invalid JSON for key=%s: %s",
                            key,
                            exc,
                        )
                        continue

                    writer.writerow(
                        [
                            acct_id,
                            obj.get("txn_id", ""),
                            obj.get("amount", 0),
                            (
                                "; ".join(obj.get("flags", []))
                                if isinstance(obj.get("flags"), list)
                                else ""
                            ),
                            obj.get("timestamp", ""),
                        ]
                    )

        _logger.info("✅ Anomalies exported to %s at %s", filepath, datetime.utcnow().isoformat())

    except Exception as exc:
        _logger.exception("[anomaly_export] Failed to write CSV: %s", exc)
