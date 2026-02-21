# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/identity.py

import logging
import warnings

from app.utils.telemetry import log_identity_event as canonical_logger

# This module is deprecated. Target removal by Q4 2025.
warnings.warn(
    "app.utils.identity is deprecated. Use app.utils.telemetry.log_identity_event instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


def log_identity_event(
    user_id: str, event_type: str, details: dict | None = None, reason: str = None, **kwargs
):
    """
    Deprecated: Logs an event related to user identity.
    This function is a wrapper for app.utils.telemetry.log_identity_event.
    Please update your imports to use the canonical logger directly.
    """
    # Log a warning to the application logger for structured monitoring
    logger.warning("Deprecated log_identity_event called from app.utils.identity")

    if details is None:
        details = {}

    # Merge 'details' into kwargs, so they are passed to the canonical logger's **meta parameter
    merged_kwargs = {**details, **kwargs}

    # Call the canonical function, which handles all the Redis and DB logic
    return canonical_logger(event_type=event_type, user_id=user_id, reason=reason, **merged_kwargs)
