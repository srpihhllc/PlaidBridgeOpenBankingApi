# app/workers/polsia_tasks.py

import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlsplit

from celery import Celery, Task

from app.services.polsia_client import PolsiaClient
from app.services.polsia_engine import PolsiaNightCycleRunner

logger = logging.getLogger(__name__)

# Require an explicit Redis broker URL. Accept redis:// for staging services
# that do not support TLS and rediss:// when the broker has TLS enabled.
broker_url = os.environ["CELERY_BROKER_URL"]
if urlsplit(broker_url).scheme not in {"redis", "rediss"}:
    raise RuntimeError("CELERY_BROKER_URL must use redis:// or rediss://")

celery = Celery(
    "finbrain_polsia",
    broker=broker_url,
)

# Restrict task messages to JSON; do not enable pickle for an external broker.
celery.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    enable_utc=True,
    timezone="UTC",
)


@celery.task(bind=True, max_retries=3)
def run_nightly_polsia_cycle(
    self: Task,
    company_id: str = "comp_plaidbridge_01",
) -> dict[str, Any]:
    """Run the autonomous nightly cycle over Plaid banking metrics."""

    async def _execute() -> dict[str, Any]:
        client = PolsiaClient()
        try:
            runner = PolsiaNightCycleRunner(client)
            plaid_summary = {
                "status": "active",
                "trigger": "scheduled_night_beat",
            }
            result = await runner.trigger_night_task(
                company_id=company_id,
                plaid_financial_summary=plaid_summary,
            )
            logger.info("Nightly Polsia cycle completed for %s", company_id)
            return result.model_dump()
        except Exception as exc:
            logger.exception("Nightly Polsia task failed for %s", company_id)
            raise self.retry(exc=exc, countdown=60) from exc
        finally:
            await client.close()

    return asyncio.run(_execute())


@celery.task(bind=True, max_retries=3)
def process_polsia_webhook_event(
    self: Task,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Process a Polsia webhook event."""

    task_id = event_data.get("task_id")
    event_type = event_data.get("event")
    

    logger.info(
        "Processing Polsia event %r for task %s",
        event_type,
        task_id,
    )

    if event_type == "task.completed":
        logger.info("Polsia task %s completed successfully", task_id)
    elif event_type == "task.failed":
        # Avoid logging the raw error payload, which may contain sensitive data.
        logger.error("Polsia task %s reported failure", task_id)
    else:
        logger.warning("Unhandled Polsia event type: %s", event_type)

    return {
        "status": "processed",
        "task_id": task_id,
    }
