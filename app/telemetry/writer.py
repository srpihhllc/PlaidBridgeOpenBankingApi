# app/telemetry/writer.py

import json
import logging
import time
import uuid

from flask import current_app
from sqlalchemy.exc import OperationalError, SQLAlchemyError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 0.25


def safe_record_trace_event(session_factory, trace_event):
    """
    Try to commit a telemetry trace_event.
    - Retries on OperationalError
    - Falls back to Redis queue if DB is unavailable
    """
    for attempt in range(1, MAX_RETRIES + 1):
        sess = session_factory()
        try:
            sess.add(trace_event)
            sess.commit()
            sess.close()
            return True
        except OperationalError as op_err:
            sess.rollback()
            sess.close()
            logger.warning("Telemetry DB offline (OperationalError): %s", op_err)
            time.sleep(RETRY_BACKOFF_SEC * attempt)
            continue
        except SQLAlchemyError as sa_err:
            sess.rollback()
            sess.close()
            logger.error("Telemetry DB write failed: %s", sa_err)
            break

    # fallback to Redis
    try:
        payload = {
            "id": str(uuid.uuid4()),
            "event_type": getattr(trace_event, "event_type", "unknown"),
            "timestamp": getattr(trace_event, "timestamp", None),
            "detail": getattr(trace_event, "detail", None),
        }
        r = current_app.extensions.get("redis_client") or getattr(current_app, "redis_client", None)
        if r:
            r.rpush("telemetry_fallback_queue", json.dumps(payload))
            logger.info("Queued telemetry event to redis fallback queue: %s", payload["id"])
    except Exception as e:
        logger.error("Failed to enqueue telemetry fallback: %s", e)
    return False
