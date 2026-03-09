# =============================================================================
# FILE: app/utils/email_utils.py
# DESCRIPTION: Cockpit-grade email dispatch via SendGrid with PDF attachment.
# =============================================================================

import base64
import logging
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Attachment, Disposition, FileContent, FileName, FileType, Mail

from app.utils.redis_utils import set_job_status  # cockpit Redis tracking
from app.utils.telemetry import _get_safe_redis_client  # TTL pulse emitter

_logger = logging.getLogger(__name__)

# Load API key and sender email from environment
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@yourdomain.com")


def send_email_with_attachment(
    to_email: str,
    subject: str,
    content: str,
    filename: str,
    file_bytes: bytes,
    job_id: str | None = None,
) -> None:
    """
    Sends an email with a file attachment via SendGrid.
    Tracks success/failure in Redis for cockpit visibility.
    Emits TTL pulses for cockpit overlays.
    """
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not configured")

    if not all([to_email, subject, content, filename, file_bytes]):
        raise ValueError("Missing required email fields")

    try:
        # Encode file for SendGrid attachment
        encoded_file = base64.b64encode(file_bytes).decode()

        attachment = Attachment(
            FileContent(encoded_file),
            FileName(filename),
            FileType("application/pdf"),  # adjust if needed
            Disposition("attachment"),
        )

        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=content,
        )
        message.attachment = attachment

        # Send the email
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        # Log success to Redis
        if job_id:
            set_job_status(
                job_id,
                "sent",
                {
                    "recipient": to_email,
                    "filename": filename,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                },
            )

        # Cockpit TTL pulse for successful send
        _get_safe_redis_client(pulse_key="ttl:email:dispute_blast", ttl=300)

        _logger.info("Email sent successfully to %s (job_id=%s)", to_email, job_id)

    except Exception as e:
        _logger.exception("Failed to send email to %s (job_id=%s)", to_email, job_id)

        # Log failure to Redis
        if job_id:
            set_job_status(
                job_id,
                "failed",
                {"recipient": to_email, "filename": filename, "error": str(e)},
            )

        # Cockpit TTL pulse for failed send
        _get_safe_redis_client(pulse_key="ttl:email:dispute_blast_error", ttl=300)
        raise


def send_password_reset_email(to_email: str, reset_token: str, job_id: str | None = None) -> None:
    """
    Sends a password reset email using the existing email sending infrastructure.
    This function is a specific-purpose wrapper for reset tokens.
    """
    subject = "Plaid Bridge Open Banking API - Password Reset"
    content = f"""
        <h1>Password Reset</h1>
        <p>Hello,</p>
        <p>
            You have requested to reset your password. Please use the following
            token to reset your password:
        </p>
        <p><strong>{reset_token}</strong></p>
        <p>If you did not request this, please ignore this email.</p>
    """

    # For text-only emails, we pass a placeholder file attachment.
    # In production, consider a dedicated function for text-only emails.
    send_email_with_attachment(
        to_email,
        subject,
        content,
        filename="reset_info.txt",
        file_bytes=b"Password reset information.",
        job_id=job_id,
    )
