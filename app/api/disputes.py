# app/api/disputes.py

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.dispute_service import process_dispute
from app.utils.cockpit_tracker import (
    mark_job_failed,
    mark_job_queued,
    mark_job_sent,
    start_batch,
)
from app.utils.redis_utils import get_redis_client as get_redis

router = APIRouter()


class StartBatchRequest(BaseModel):
    total: int
    origin: str


class SubmitDisputeRequest(BaseModel):
    accountNumber: str
    transactionId: str
    reason: str
    batch_id: str
    job_id: str


@router.post("/start")
def start_dispute_batch(req: StartBatchRequest) -> dict[str, str]:
    batch_id = str(uuid.uuid4())
    start_batch(batch_id, total=req.total, origin=req.origin)

    # Pre-assign a job ID for frontend tracking.
    job_id = str(uuid.uuid4())
    return {"batch_id": batch_id, "job_id": job_id}


@router.post("/submit")
def submit_dispute(req: SubmitDisputeRequest) -> dict[str, str]:
    origin = "dispute_form"
    job_data: dict[str, str] = {
        "account": req.accountNumber,
        "transaction": req.transactionId,
    }

    mark_job_queued(req.job_id, job_data)

    try:
        process_dispute(
            account_number=req.accountNumber,
            transaction_id=req.transactionId,
            reason=req.reason,
        )
        mark_job_sent(
            req.job_id,
            job_data,
            req.batch_id,
            origin,
        )
        return {"status": "queued"}
    except Exception as exc:
        mark_job_failed(
            req.job_id,
            job_data,
            req.batch_id,
            origin,
            str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail="Dispute submission failed",
        ) from exc


@router.get("/job-status/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    redis_client = get_redis()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    status = redis_client.get(f"cockpit:job:{job_id}:status")
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    if isinstance(status, (bytes, bytearray)):
        return {"status": status.decode("utf-8")}

    return {"status": str(status)}