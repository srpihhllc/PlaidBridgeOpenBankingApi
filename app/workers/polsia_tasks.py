# app/workers/polsia_tasks.py

import asyncio
import logging
from typing import Any

from celery import Celery, Task

from app.services.polsia_client import PolsiaClient
from app.services.polsia_engine import PolsiaNightCycleRunner

logger = logging.getLogger(__name__)

# Use a real Celery instance here because app.extensions does not define `celery`.
# Configure its broker/backend through your Celery configuration or environment.
celery = Celery("finbrain_polsia")


@celery.task(bind=True, max_retries=3)
def run_nightly_polsia_cycle(
    self: Task,
    company_id: str = "comp_plaidbridge_01",
) -> dict[str, Any]:
    """Run the autonomous nightly cycle over Plaid banking metrics."""

    async def _execute() -> dict[str, Any]:
        client = PolsiaClient()
        runner = PolsiaNightCycleRunner(client)

        try:
            plaid_summary = {
                "status": "active",
                "trigger": "scheduled_night_beat",
            }
            result = await runner.trigger_night_task(
                company_id=company_id,
                plaid_financial_summary=plaid_summary,
            )
            logger.info(
                "Nightly Polsia cycle completed for %s: %s",
                company_id,
                result,
            )
            return result.model_dump()
        except Exception as exc:
            logger.exception("Nightly Polsia task failed")
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
    payload = event_data.get("payload") or {}

    logger.info(
        "Processing background Polsia event %r for task %s",
        event_type,
        task_id,
    )

    if event_type == "task.completed":
        logger.info(
            "Task %s completed successfully: %s",
            task_id,
            payload.get("result"),
        )
    elif event_type == "task.failed":
        logger.error(
            "Task %s failed: %s",
            task_id,
            payload.get("error"),
        )
    else:
        logger.warning("Unhandled event type: %s", event_type)

    return {
        "status": "processed",
        "task_id": task_id,
    }