# =============================================================================
# FILE: app/utils/trace_log.py
# DESCRIPTION: Deprecated wrapper for identity event logging.
#              Target removal by Q4 2025.
# =============================================================================

import logging
import warnings
from typing import Any

from app.utils.telemetry import increment_counter
from app.utils.telemetry import log_identity_event as canonical_logger

logger = logging.getLogger(__name__)

# Deprecation warning on import
warnings.warn(
    "app.utils.trace_log is deprecated. Use app.utils.telemetry.log_identity_event instead.",
    DeprecationWarning,
    stacklevel=2,
)


# TODO: Remove after Q4 2025
def log_identity_event(
    user_id: int | None = None,
    event_type: str | None = None,
    details: dict[str, Any] | None = None,
    **kwargs,
) -> str:
    """
    DEPRECATED WRAPPER: Delegates to app.utils.telemetry.log_identity_event.
    Increments a telemetry counter so maintainers can quantify legacy usage.
    """
    increment_counter("identity.trace_log_deprecated")

    warnings.warn(
        "Use app.utils.telemetry.log_identity_event directly",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.warning("Deprecated log_identity_event called from app.utils.trace_log")

    return canonical_logger(user_id=user_id, event_type=event_type, details=details, **kwargs)
