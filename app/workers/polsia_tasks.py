#app/workers/polsia_tasks.py

import asyncio
import logging
from typing import Any, Dict

# Assuming Celery instance is configured in app.extensions or app.workers
try:
    from app.extensions import celery
except ImportError:
    from celery import Celery
    celery = Celery("finbrain_polsia")

from app.services.polsia_client import PolsiaClient
from app.services.polsia_engine import PolsiaNightCycleRunner

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def run_nightly_polsia_cycle(self, company_id: str = "comp_plaidbridge_01"):
    """Celery task running the autonomous nightly cycle over Plaid banking metrics."""
    async def _execute():
        client = PolsiaClient()
        runner = PolsiaNightCycleRunner(client)
        try:
            plaid_summary = {
                "status": "active",
                "trigger": "scheduled_night_beat",
            }
            res = await runner.trigger_night_task(company_id=company_id, plaid_financial_summary=plaid_summary)
            logger.info(f"Nightly Polsia cycle completed for {company_id}: {res}")
            return res.model_dump()
        except Exception as exc:
            logger.error(f"Nightly Polsia task failed: {exc}")
            raise self.retry(exc=exc, countdown=60)
        finally:
            await client.close()

    return asyncio.run(_execute())


@celery.task(bind=True, max_retries=3)
def process_polsia_webhook_event(self, event_data: Dict[str, Any]):
    """Processes Polsia webhook events asynchronously."""
    task_id = event_data.get("task_id")
    event_type = event_data.get("event")
    payload = event_data.get("payload", {})

    logger.info(f"Processing background Polsia event '{event_type}' for task {task_id}")

    if event_type == "task.completed":
        result = payload.get("result")
        logger.info(f"Task {task_id} completed successfully: {result}")
    elif event_type == "task.failed":
        error = payload.get("error")
        logger.error(f"Task {task_id} failed: {error}")
    else:
        logger.warning(f"Unhandled event type: {event_type}")

    return {"status": "processed", "task_id": task_id}