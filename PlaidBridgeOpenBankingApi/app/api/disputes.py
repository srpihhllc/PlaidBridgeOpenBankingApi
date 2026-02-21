# app/api/disputes.py

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# These in-repo modules currently lack stubs/py.typed; silence the import-untyped mypy error.
from app.services.dispute_service import process_dispute  # type: ignore[import-untyped]
from app.utils.cockpit_tracker import (  # type: ignore[import-untyped]
    mark_job_failed,
    mark_job_queued,
    mark_job_sent,
    start_batch,
)
from app.utils.redis_utils import get_redis_client as get_redis  # ✅ updated import

router = APIRouter()


# --- Request Models ---
class StartBatchRequest(BaseModel):
    total: int
    origin: str


class SubmitDisputeRequest(BaseModel):
    accountNumber: str
    transactionId: str
    reason: str
    batch_id: str
    job_id: str


# --- Routes ---
@router.post("/start")
def start_dispute_batch(req: StartBatchRequest):
    batch_id = str(uuid.uuid4())
    start_batch(batch_id, total=req.total, origin=req.origin)
    job_id = str(uuid.uuid4())  # Pre‑assign job for frontend tracking
    return {"batch_id": batch_id, "job_id": job_id}


@router.post("/submit")
def submit_dispute(req: SubmitDisputeRequest):
    origin = "dispute_form"
    mark_job_queued(req.job_id, {"account": req.accountNumber, "transaction": req.transactionId})

    try:
        # Your actual dispute processing logic
        process_dispute(
            account_number=req.accountNumber,
            transaction_id=req.transactionId,
            reason=req.reason,
        )
        mark_job_sent(
            req.job_id,
            {"account": req.accountNumber, "transaction": req.transactionId},
            req.batch_id,
            origin,
        )
        return {"status": "queued"}
    except Exception as e:
        mark_job_failed(
            req.job_id,
            {"account": req.accountNumber, "transaction": req.transactionId},
            req.batch_id,
            origin,
            str(e),
        )
        raise HTTPException(status_code=500, detail="Dispute submission failed") from e


@router.get("/job-status/{job_id}")
def get_job_status(job_id: str):
    r = get_redis()
    if r is None:
        # Redis not available — surface a 503 so callers know it's a service/unavailability issue
        raise HTTPException(status_code=503, detail="Redis unavailable")
    status = r.get(f"cockpit:job:{job_id}:status")
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    # status is expected to be bytes; decode safely if needed
    if isinstance(status, (bytes, bytearray)):
        return {"status": status.decode("utf-8")}
    return {"status": str(status)}
