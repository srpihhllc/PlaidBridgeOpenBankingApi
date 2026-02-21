# app/letters/dispute_blast.py

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict, cast

from app.extensions import db
from app.letters.bureaus import BUREAUS
from app.letters.pdf_writer import narratable_filename, write_pdf
from app.letters.render_engine import render_letter
from app.models.dispute_log import DisputeLog
from app.models.schema_event import SchemaEvent
from app.models.user import User
from app.utils.email_utils import send_email_with_attachment
from app.utils.redis_utils import increment_progress, init_progress, set_job_status

logger = logging.getLogger(__name__)


class Bureau(TypedDict):
    name: str
    email: str


@dataclass
class DisputeJobResult:
    bureau: str
    status: str
    pdf_path: str | None
    content_hash: str | None
    error: str | None = None


async def _retry_async(
    func: Callable[[], Any],
    retries: int = 3,
    delay_seconds: float = 1.0,
    backoff: float = 2.0,
    context: str = "",
) -> Any:
    attempt = 0
    while True:
        try:
            return func()
        except Exception as e:
            attempt += 1
            logger.warning(
                "Retryable error in %s (attempt %s/%s): %s",
                context,
                attempt,
                retries,
                e,
            )
            if attempt >= retries:
                logger.error("Exhausted retries in %s: %s", context, e)
                raise
            await asyncio.sleep(delay_seconds)
            delay_seconds *= backoff


async def _process_bureau_dispute(
    user: User,
    bureau: Bureau,
    template_name: str,
    user_payload: dict[str, Any],
    metadata: dict[str, Any],
    blast_id: str | None,
) -> DisputeJobResult:
    job_id = f"dispute:job:{user.id}:{bureau['name']}"
    set_job_status(job_id, "queued", {"bureau": bureau["name"]})
    logger.info(
        "Dispute job queued",
        extra={"job_id": job_id, "bureau": bureau["name"], "user_id": user.id},
    )

    content_hash: str | None = None
    pdf_path: str | None = None
    log_status = "failed"
    email_status = "error"
    error_msg: str | None = None

    try:
        # render_letter expects a plain dict; make sure we pass a dict not a TypedDict
        letter_body = render_letter(
            template_name, user=user_payload, bureau=dict(bureau), metadata=metadata
        )
        content_hash = hashlib.sha256(letter_body.encode("utf-8")).hexdigest()

        content_lines = letter_body.splitlines()
        pdf_filename = narratable_filename(prefix=f"dispute_{user.id}_{bureau['name']}", ext="pdf")
        pdf_path = write_pdf(
            content_lines,
            filename=pdf_filename,
            title=f"Credit Dispute Letter: {template_name}",
            operator=user.full_name,
        )

        def _send() -> None:
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()
            send_email_with_attachment(
                to_email=bureau["email"],
                subject=f"Dispute Letter - {user.full_name}",
                content="Please see attached.",
                filename=pdf_filename,
                file_bytes=file_bytes,
                job_id=job_id,
            )

        await _retry_async(_send, context=f"send_email:{job_id}")

        set_job_status(job_id, "sent", {"bureau": bureau["name"], "pdf": pdf_filename})
        # Only increment progress when we have a concrete blast_id (not None)
        if blast_id:
            increment_progress(blast_id, "sent")
        log_status = "sent"
        email_status = "sent"

        logger.info(
            "Dispute job sent",
            extra={
                "job_id": job_id,
                "bureau": bureau["name"],
                "user_id": user.id,
                "pdf": pdf_filename,
            },
        )

    except Exception as e:
        error_msg = str(e)
        set_job_status(job_id, "failed", {"bureau": bureau["name"], "error": error_msg})
        logger.exception(
            "Dispute job failed",
            extra={"job_id": job_id, "bureau": bureau["name"], "user_id": user.id},
        )

    db.session.add(
        DisputeLog(
            user_id=user.id,
            template_title=template_name,
            bureau=bureau["name"],
            method="email",
            email_status=email_status,
            sendgrid_id=None,
            content_hash=content_hash,
            delivery_ts=datetime.utcnow(),
            status=log_status,
        )
    )
    db.session.add(
        SchemaEvent(
            event_type=f"DISPUTE_{log_status.upper()}",
            origin="dispute_blast",
            detail=f"Letter {log_status} to {bureau['name']} for user_id={user.id}",
        )
    )

    return DisputeJobResult(
        bureau=bureau["name"],
        status=log_status,
        pdf_path=pdf_path,
        content_hash=content_hash,
        error=error_msg,
    )


async def send_dispute_blast_async(
    user_id: int,
    template_name: str,
    metadata: dict[str, Any] | None = None,
    blast_id: str | None = None,
) -> list[dict[str, Any]]:
    user = User.query.get(user_id)
    if not user:
        raise ValueError(f"Invalid user ID: {user_id}")

    metadata = metadata or {}

    user_payload: dict[str, Any] = {
        "name": user.full_name,
        "address": user.address,
        "city": user.city,
        "state": user.state,
        "zip": user.zip,
        "dob": user.dob.strftime("%m/%d/%Y") if user.dob else "",
        "ssn_last4": user.ssn_last4,
    }

    # Only initialize progress if we have a concrete blast id
    if blast_id:
        init_progress(blast_id, total=len(BUREAUS))

    tasks: list[Awaitable[DisputeJobResult]] = []
    # BUREAUS may be untyped at import site; cast each item to the Bureau TypedDict.
    for bureau in BUREAUS:
        tasks.append(
            _process_bureau_dispute(
                user=user,
                bureau=cast(Bureau, bureau),
                template_name=template_name,
                user_payload=user_payload,
                metadata=metadata,
                blast_id=blast_id,
            )
        )

    results: list[DisputeJobResult] = await asyncio.gather(*tasks, return_exceptions=False)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to commit dispute blast results", extra={"user_id": user.id})
        raise

    return [
        {
            "bureau": r.bureau,
            "status": r.status,
            "pdf_path": r.pdf_path,
            "content_hash": r.content_hash,
            "error": r.error,
        }
        for r in results
    ]


def send_dispute_blast(
    user_id: int,
    template_name: str,
    metadata: dict[str, Any] | None = None,
    blast_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Sync entrypoint for WSGI/Flask callers.
    Runs the async orchestrator in a private event loop.
    """
    return asyncio.run(
        send_dispute_blast_async(
            user_id=user_id,
            template_name=template_name,
            metadata=metadata,
            blast_id=blast_id,
        )
    )
