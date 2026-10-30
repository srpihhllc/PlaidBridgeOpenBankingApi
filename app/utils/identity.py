# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/identity.py

import logging
import warnings
from typing import Any

from app.utils.telemetry import log_identity_event as canonical_logger

# This module is deprecated. Target removal by Q4 2025.
warnings.warn(
    "app.utils.identity is deprecated. Use "
    "app.utils.telemetry.log_identity_event instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


def log_identity_event(
    user_id: str,
    event_type: str,
    details: dict[str, Any] | None = None,
    reason: str | None = None,
    **kwargs: Any,
) -> Any:
    """
    Deprecated wrapper for app.utils.telemetry.log_identity_event.

    Please update imports to use the canonical logger directly.
    """
    logger.warning("Deprecated log_identity_event called from app.utils.identity")

    # Treat details and extra keyword arguments as metadata for the canonical logger.
    metadata: dict[str, Any] = {**(details or {}), **kwargs}

    # The explicit arguments take precedence over values supplied as metadata.
    metadata.pop("user_id", None)
    metadata.pop("event_type", None)
    metadata.pop("reason", None)

    if reason is not None:
        metadata["reason"] = reason

    return canonical_logger(
        event_type=event_type,
        user_id=user_id,
        **metadata,
    )