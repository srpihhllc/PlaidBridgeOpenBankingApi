
# app/workers/polsia_tasks.py



import asyncio

import logging

import os

from typing import Any

from urllib.parse import urlsplit



from celery import Celery, Task



from app.services.polsia_client import PolsiaClient

from app.services.polsia_engine import PolsiaNightCycleRunner

from app.services.polsia_memory import PolsiaMemoryStore



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





def _build_nightly_telemetry(company_id: str) -> dict[str, Any]:

    """Assemble live Plaid/ledger metrics + prior learned Polsia insights."""

    memory = PolsiaMemoryStore()

    prior_insights = memory.get_recent_insights(company_id=company_id, limit=5)

    telemetry: dict[str, Any] = {

        "status": "active",

        "trigger": "scheduled_night_beat",

        "prior_learnings": prior_insights,

    }



    try:

        from app import create_app

        from app.extensions import db

        from app.models.bank_transaction import BankTransaction

        from app.models.credit_ledger import CreditLedger

        from app.models.fraud_report import FraudReport



        app = create_app()

        with app.app_context():

            telemetry["metrics"] = {

                "bank_transactions_count": db.session.query(BankTransaction).count(),

                "credit_ledger_count": db.session.query(CreditLedger).count(),

                "fraud_reports_count": db.session.query(FraudReport).count(),

            }

    except Exception as exc:

        logger.debug("Nightly telemetry DB snapshot skipped: %s", exc)



    return telemetry





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

            plaid_summary = _build_nightly_telemetry(company_id)

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

    """Process a Polsia webhook event and persist learned outcomes."""



    task_id = event_data.get("task_id")

    event_type = event_data.get("event")

    memory = PolsiaMemoryStore()



    logger.info(

        "Processing Polsia event %r for task %s",

        event_type,

        task_id,

    )



    if event_type == "task.completed":

        memory.record_outcome(event_data)

        logger.info("Polsia task %s completed and stored in FinBrain memory", task_id)

    elif event_type == "task.failed":

        memory.record_outcome(event_data)

        # Avoid logging the raw error payload, which may contain sensitive data.

        logger.error("Polsia task %s reported failure (recorded in memory)", task_id)

    else:

        logger.warning("Unhandled Polsia event type: %s", event_type)



    return {

        "status": "processed",

        "task_id": task_id,

    }

